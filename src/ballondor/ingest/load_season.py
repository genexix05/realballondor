"""Load one season of FotMob parquet + scores into Postgres.

Identities go through ``external_ids`` (fotmob / opta), never through bare names,
so ``Vitinha`` and ``Vítinha`` collapse to the same player.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ballondor.ingest.seed import get_competition_id, seed_competitions

SOURCE = "fotmob"
NATIONAL = {"INT-World Cup", "INT-Euro", "INT-Copa America"}
STAT_COLUMNS = [
    "minutes", "started", "position_group", "rating", "goals", "assists",
    "shots", "shots_on_target", "xg", "xa", "passes", "passes_completed",
    "key_passes", "dribbles", "dribbles_completed", "tackles", "interceptions",
    "clearances", "blocks", "duels_won", "aerial_duels", "aerial_duels_won",
    "recoveries", "fouls", "fouls_won", "yellow_cards", "red_cards",
]


def _none(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    return value


def _int(value: Any) -> int | None:
    value = _none(value)
    if value is None or value == "":
        return None
    return int(float(value))


def _float(value: Any) -> float | None:
    value = _none(value)
    if value is None or value == "":
        return None
    return float(value)


def _str(value: Any) -> str | None:
    value = _none(value)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _kickoff(value: Any) -> datetime | None:
    value = _none(value)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _register(conn, entity_type: str, entity_id: int, source: str, key: str) -> None:
    conn.execute(
        """
        INSERT INTO external_ids (entity_type, entity_id, source, external_key)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (entity_type, source, external_key)
        DO UPDATE SET entity_id = EXCLUDED.entity_id
        """,
        (entity_type, entity_id, source, str(key)),
    )


def _lookup(conn, entity_type: str, source: str, key: str | None) -> int | None:
    if not key:
        return None
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT entity_id FROM external_ids
            WHERE entity_type = %s AND source = %s AND external_key = %s
            """,
            (entity_type, source, str(key)),
        )
        row = cur.fetchone()
        return int(row["entity_id"]) if row else None


def upsert_team(conn, fotmob_id: str, name: str, team_type: str) -> int:
    existing = _lookup(conn, "team", SOURCE, fotmob_id)
    if existing:
        conn.execute(
            "UPDATE teams SET name = COALESCE(%s, name), type = %s WHERE team_id = %s",
            (name, team_type, existing),
        )
        return existing
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO teams (name, type)
            VALUES (%s, %s)
            ON CONFLICT (name, type) DO UPDATE SET name = EXCLUDED.name
            RETURNING team_id
            """,
            (name, team_type),
        )
        team_id = int(cur.fetchone()["team_id"])
    _register(conn, "team", team_id, SOURCE, fotmob_id)
    return team_id


def upsert_player(
    conn,
    *,
    opta_id: str | None,
    fotmob_id: str | None,
    name: str,
    country: str | None,
    country_code: str | None,
    position: str | None,
    age: int | None = None,
) -> int:
    player_id = _lookup(conn, "player", "opta", opta_id) if opta_id else None
    if player_id is None:
        player_id = _lookup(conn, "player", SOURCE, fotmob_id)
    if player_id is None:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO players (
                    name, nationality, primary_position, country, country_code, age
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING player_id
                """,
                (name, country, position, country, country_code, age),
            )
            player_id = int(cur.fetchone()["player_id"])
    else:
        conn.execute(
            """
            UPDATE players SET
                name = %s,
                nationality = COALESCE(%s, nationality),
                primary_position = COALESCE(%s, primary_position),
                country = COALESCE(%s, country),
                country_code = COALESCE(%s, country_code),
                age = COALESCE(%s, age)
            WHERE player_id = %s
            """,
            (name, country, position, country, country_code, age, player_id),
        )
    if opta_id:
        _register(conn, "player", player_id, "opta", opta_id)
    if fotmob_id:
        _register(conn, "player", player_id, SOURCE, fotmob_id)
    return player_id


def load_matches(conn, matches: pd.DataFrame) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for row in matches.itertuples(index=False):
        code = row.competition_code
        competition_id = get_competition_id(conn, code)
        kind = "national" if code in NATIONAL else "club"
        home_id = upsert_team(conn, str(row.home_team_id), row.home_team, kind)
        away_id = upsert_team(conn, str(row.away_team_id), row.away_team, kind)
        fotmob_match_id = str(row.fotmob_match_id)
        kickoff = _kickoff(row.kickoff_utc)
        match_date = None if kickoff is None else kickoff.date()
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT match_id FROM matches
                WHERE source = %s AND source_match_id = %s
                """,
                (SOURCE, fotmob_match_id),
            )
            found = cur.fetchone()
            if found is None:
                cur.execute(
                    """
                    SELECT match_id FROM matches
                    WHERE competition_id = %s AND date = %s
                      AND home_team_id = %s AND away_team_id = %s
                    """,
                    (competition_id, match_date, home_id, away_id),
                )
                found = cur.fetchone()
            payload = (
                match_date,
                row.season,
                competition_id,
                _str(row.stage),
                home_id,
                away_id,
                _int(row.home_score),
                _int(row.away_score),
                _str(row.venue),
                _int(row.attendance),
                SOURCE,
                fotmob_match_id,
                kickoff,
                _str(row.coverage_level),
                _int(row.player_rows),
                _str(row.referee),
                _str(row.venue_city),
                _str(row.venue_country),
                _int(row.venue_capacity),
            )
            if found:
                cur.execute(
                    """
                    UPDATE matches SET
                        date = %s, season = %s, competition_id = %s, stage = %s,
                        home_team_id = %s, away_team_id = %s, home_score = %s,
                        away_score = %s, venue = %s, attendance = %s, source = %s,
                        source_match_id = %s, kickoff_utc = %s, coverage_level = %s,
                        player_rows = %s, referee = %s, venue_city = %s,
                        venue_country = %s, venue_capacity = %s
                    WHERE match_id = %s
                    RETURNING match_id
                    """,
                    (*payload, int(found["match_id"])),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO matches (
                        date, season, competition_id, stage,
                        home_team_id, away_team_id, home_score, away_score,
                        venue, attendance, source, source_match_id,
                        kickoff_utc, coverage_level, player_rows, referee,
                        venue_city, venue_country, venue_capacity
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING match_id
                    """,
                    payload,
                )
            match_id = int(cur.fetchone()["match_id"])
        _register(conn, "match", match_id, SOURCE, fotmob_match_id)
        mapping[fotmob_match_id] = match_id
    return mapping


def load_players(conn, stats: pd.DataFrame) -> tuple[dict[str, int], dict[str, int]]:
    """Return (opta_id -> player_id, fotmob_id -> player_id)."""
    opta_map: dict[str, int] = {}
    fotmob_map: dict[str, int] = {}
    people = (
        stats.sort_values("minutes", ascending=False)
        .drop_duplicates("fotmob_player_id", keep="first")
    )
    for row in people.itertuples(index=False):
        opta_id = _str(getattr(row, "opta_player_id", None))
        fotmob_id = _str(row.fotmob_player_id)
        player_id = upsert_player(
            conn,
            opta_id=opta_id,
            fotmob_id=fotmob_id,
            name=row.player,
            country=_str(getattr(row, "country", None)),
            country_code=_str(getattr(row, "country_code", None)),
            position=_str(row.position_group),
            age=_int(getattr(row, "age", None)),
        )
        if opta_id:
            opta_map[opta_id] = player_id
        if fotmob_id:
            fotmob_map[fotmob_id] = player_id
    return opta_map, fotmob_map


def refresh_player_ages(conn, stats: pd.DataFrame) -> int:
    """Latest FotMob lineup age per player, keyed by fotmob_player_id."""
    if "age" not in stats.columns:
        return 0
    order = "kickoff_utc" if "kickoff_utc" in stats.columns else "minutes"
    latest = (
        stats.dropna(subset=["age", "fotmob_player_id"])
        .sort_values(order)
        .drop_duplicates("fotmob_player_id", keep="last")
    )
    rows: list[tuple[int, str]] = []
    for row in latest.itertuples(index=False):
        age = _int(row.age)
        fotmob_id = _str(row.fotmob_player_id)
        if age is None or fotmob_id is None:
            continue
        rows.append((age, fotmob_id))
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.execute("CREATE TEMP TABLE tmp_ages (age SMALLINT, fotmob_id TEXT)")
        cur.executemany("INSERT INTO tmp_ages (age, fotmob_id) VALUES (%s, %s)", rows)
        cur.execute(
            """
            UPDATE players p
            SET age = t.age
            FROM tmp_ages t
            JOIN external_ids e
              ON e.entity_type = 'player'
             AND e.source = %s
             AND e.external_key = t.fotmob_id
            WHERE e.entity_id = p.player_id
            """,
            (SOURCE,),
        )
        cur.execute("DROP TABLE tmp_ages")
    return len(rows)


def _player_id(row, opta_map: dict[str, int], fotmob_map: dict[str, int]) -> int | None:
    opta_id = _str(getattr(row, "opta_player_id", None))
    fotmob_id = _str(getattr(row, "fotmob_player_id", None))
    if opta_id and opta_id in opta_map:
        return opta_map[opta_id]
    if fotmob_id and fotmob_id in fotmob_map:
        return fotmob_map[fotmob_id]
    return None


def load_player_match_stats(
    conn,
    stats: pd.DataFrame,
    match_map: dict[str, int],
    opta_map: dict[str, int],
    fotmob_map: dict[str, int],
    team_map: dict[str, int],
) -> int:
    rows = []
    extra_keys = [
        "opta_player_id", "fotmob_player_id", "npxg", "saves", "goals_prevented",
        "goals_conceded", "save_pct", "shirt_number", "country_code",
    ]
    for row in stats.itertuples(index=False):
        match_id = match_map.get(str(row.fotmob_match_id))
        player_id = _player_id(row, opta_map, fotmob_map)
        team_id = team_map.get(str(row.fotmob_team_id))
        if match_id is None or player_id is None or team_id is None:
            continue
        raw = {key: _none(getattr(row, key, None)) for key in extra_keys
               if hasattr(row, key)}
        rows.append(
            (
                match_id,
                player_id,
                team_id,
                _float(row.minutes),
                bool(_none(getattr(row, "started", None)))
                if _none(getattr(row, "started", None)) is not None else None,
                _str(row.position_group),
                _float(row.rating),
                _int(row.goals),
                _int(row.assists),
                _int(getattr(row, "shots", None)),
                _int(getattr(row, "shots_on_target", None)),
                _float(getattr(row, "xg", None)),
                _float(getattr(row, "xa", None)),
                _int(getattr(row, "passes", None)),
                _int(getattr(row, "passes_completed", None)),
                _int(getattr(row, "key_passes", None)),
                _int(getattr(row, "dribbles", None)),
                _int(getattr(row, "dribbles_completed", None)),
                _int(getattr(row, "tackles", None)),
                _int(getattr(row, "interceptions", None)),
                _int(getattr(row, "clearances", None)),
                _int(getattr(row, "blocks", None)),
                _int(getattr(row, "duels_won", None)),
                _int(getattr(row, "aerial_duels", None)),
                _int(getattr(row, "aerial_duels_won", None)),
                _int(getattr(row, "recoveries", None)),
                _int(getattr(row, "fouls", None)),
                _int(getattr(row, "fouls_won", None)),
                _int(getattr(row, "yellow_cards", None)),
                _int(getattr(row, "red_cards", None)),
                SOURCE,
                Jsonb(raw),
            )
        )
    sql = """
        INSERT INTO player_match_stats (
            match_id, player_id, team_id, minutes, started, position, rating,
            goals, assists, shots, shots_on_target, xg, xa, passes, passes_completed,
            key_passes, dribbles, dribbles_completed, tackles, interceptions,
            clearances, blocks, duels_won, aerial_duels, aerial_duels_won,
            recoveries, fouls, fouls_won, yellow_cards, red_cards, source, raw
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (match_id, player_id) DO UPDATE SET
            minutes = EXCLUDED.minutes,
            rating = EXCLUDED.rating,
            goals = EXCLUDED.goals,
            assists = EXCLUDED.assists,
            raw = EXCLUDED.raw
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


def load_match_scores(
    conn,
    scores: pd.DataFrame,
    match_map: dict[str, int],
    opta_map: dict[str, int],
    fotmob_map: dict[str, int],
    team_map: dict[str, int],
    season: str,
) -> int:
    rows = []
    for row in scores.itertuples(index=False):
        match_id = match_map.get(str(row.match_id))
        opta_id = _str(row.opta_player_id)
        player_id = opta_map.get(opta_id) if opta_id else None
        if player_id is None:
            player_id = fotmob_map.get(_str(getattr(row, "fotmob_player_id", None)) or "")
        team_id = team_map.get(str(row.team_id))
        if match_id is None or player_id is None or team_id is None:
            continue
        rows.append(
            (
                match_id,
                player_id,
                team_id,
                season,
                _str(row.position_group),
                _str(row.opponent),
                _float(row.minutes),
                _float(row.rating),
                _int(row.goals),
                _int(row.assists),
                _float(row.stats_score),
                _float(row.rating_score),
                _float(row.penalty_score),
                _float(row.performance),
                _float(row.reliability),
                _float(row.opponent_strength),
                _float(row.opponent_multiplier),
                _float(row.competition_weight),
                _float(row.stage_weight),
                _float(row.match_score),
                _str(row.coverage_level),
            )
        )
    sql = """
        INSERT INTO player_match_scores (
            match_id, player_id, team_id, season, position_group, opponent,
            minutes, rating, goals, assists, stats_score, rating_score,
            penalty_score, performance, reliability, opponent_strength,
            opponent_multiplier, competition_weight, stage_weight, match_score,
            coverage_level
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
        ON CONFLICT (match_id, player_id) DO UPDATE SET
            position_group = EXCLUDED.position_group,
            minutes = EXCLUDED.minutes,
            rating = EXCLUDED.rating,
            goals = EXCLUDED.goals,
            assists = EXCLUDED.assists,
            stats_score = EXCLUDED.stats_score,
            rating_score = EXCLUDED.rating_score,
            penalty_score = EXCLUDED.penalty_score,
            performance = EXCLUDED.performance,
            reliability = EXCLUDED.reliability,
            opponent_strength = EXCLUDED.opponent_strength,
            opponent_multiplier = EXCLUDED.opponent_multiplier,
            competition_weight = EXCLUDED.competition_weight,
            stage_weight = EXCLUDED.stage_weight,
            match_score = EXCLUDED.match_score,
            coverage_level = EXCLUDED.coverage_level
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


def load_index(conn, ranking: pd.DataFrame, opta_map: dict[str, int], season: str) -> int:
    rows = []
    for row in ranking.itertuples(index=False):
        opta_id = _str(row.opta_player_id)
        player_id = opta_map.get(opta_id) if opta_id else None
        if player_id is None:
            continue
        club = _str(row.club)
        club_team_id = None
        if club:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT team_id FROM teams WHERE name = %s AND type = 'club' LIMIT 1",
                    (club,),
                )
                found = cur.fetchone()
                if found:
                    club_team_id = int(found["team_id"])
        rows.append(
            (
                season,
                player_id,
                _int(row.rank),
                club_team_id,
                club,
                _str(row.position_group),
                _int(row.matches),
                _float(row.minutes),
                _int(row.goals),
                _int(row.assists),
                _float(row.mean_rating),
                _float(row.season_score),
                _float(row.mean_match_score),
                _float(row.consistency),
                _float(row.individual_score),
                _int(row.trophies) or 0,
                _float(row.trophy_score),
                _float(row.index_value),
            )
        )
    sql = """
        INSERT INTO season_index (
            season, player_id, rank, club_team_id, club, position_group,
            matches, minutes, goals, assists, mean_rating, season_score,
            mean_match_score, consistency, individual_score, trophies,
            trophy_score, index_value
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (season, player_id) DO UPDATE SET
            rank = EXCLUDED.rank,
            club_team_id = EXCLUDED.club_team_id,
            club = EXCLUDED.club,
            position_group = EXCLUDED.position_group,
            matches = EXCLUDED.matches,
            minutes = EXCLUDED.minutes,
            goals = EXCLUDED.goals,
            assists = EXCLUDED.assists,
            mean_rating = EXCLUDED.mean_rating,
            season_score = EXCLUDED.season_score,
            mean_match_score = EXCLUDED.mean_match_score,
            consistency = EXCLUDED.consistency,
            individual_score = EXCLUDED.individual_score,
            trophies = EXCLUDED.trophies,
            trophy_score = EXCLUDED.trophy_score,
            index_value = EXCLUDED.index_value
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


def load_trophies(
    conn,
    champions: pd.DataFrame,
    detail: pd.DataFrame,
    opta_map: dict[str, int],
    team_map: dict[str, int],
    season: str,
) -> None:
    for row in champions.itertuples(index=False):
        competition_id = get_competition_id(conn, row.competition_code)
        winner_id = team_map.get(str(row.winner_id))
        runner_id = team_map.get(str(row.runner_up_id))
        conn.execute(
            """
            INSERT INTO season_trophies (
                season, competition_id, winner_team_id, runner_up_team_id,
                winner, runner_up, decided_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (season, competition_id) DO UPDATE SET
                winner = EXCLUDED.winner,
                runner_up = EXCLUDED.runner_up,
                decided_by = EXCLUDED.decided_by
            """,
            (
                season, competition_id, winner_id, runner_id,
                _str(row.winner), _str(row.runner_up), _str(row.decided_by),
            ),
        )
    rows = []
    for row in detail.itertuples(index=False):
        opta_id = _str(row.opta_player_id)
        player_id = opta_map.get(opta_id) if opta_id else None
        if player_id is None:
            continue
        competition_id = get_competition_id(conn, row.competition_code)
        rows.append(
            (
                season,
                player_id,
                competition_id,
                team_map.get(str(getattr(row, "team_id", ""))) if hasattr(row, "team_id") else None,
                _str(row.role),
                _float(row.share),
                _float(row.points),
            )
        )
    if not rows:
        return
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO player_trophy_credit (
                season, player_id, competition_id, team_id, role, share, points
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (season, player_id, competition_id, role) DO UPDATE SET
                share = EXCLUDED.share,
                points = EXCLUDED.points
            """,
            rows,
        )


def load_season(conn, season: str, raw_dir, processed_dir) -> dict[str, int]:
    tag = season.replace("/", "-")
    matches = pd.read_parquet(raw_dir / f"matches_full_{tag}.parquet")
    stats = pd.read_parquet(raw_dir / f"player_match_stats_full_{tag}.parquet")
    scores = pd.read_parquet(processed_dir / f"match_scores_{tag}.parquet")
    ranking = pd.read_parquet(processed_dir / f"ballondor_index_{tag}.parquet")
    ranking = ranking.rename(columns={"index": "index_value"})
    champions = pd.read_csv(processed_dir / f"champions_{tag}.csv")
    detail = pd.read_parquet(processed_dir / f"trophy_detail_{tag}.parquet")

    seed_competitions(conn)
    print(f"partidos: {len(matches):,}  filas: {len(stats):,}")

    match_map = load_matches(conn, matches)
    print(f"  matches upserted: {len(match_map):,}")

    team_map: dict[str, int] = {}
    for column_id, column_name, code in (
        ("home_team_id", "home_team", "competition_code"),
        ("away_team_id", "away_team", "competition_code"),
    ):
        kind_series = matches[code].isin(NATIONAL)
        for fotmob_id, name, is_nat in zip(
            matches[column_id].astype(str), matches[column_name], kind_series, strict=False
        ):
            if fotmob_id in team_map:
                continue
            team_map[fotmob_id] = upsert_team(
                conn, fotmob_id, name, "national" if is_nat else "club"
            )

    opta_map, fotmob_map = load_players(conn, stats)
    print(f"  players: {len(fotmob_map):,}")
    n_ages = refresh_player_ages(conn, stats)
    print(f"  ages: {n_ages:,}")

    n_stats = load_player_match_stats(conn, stats, match_map, opta_map, fotmob_map, team_map)
    print(f"  player_match_stats: {n_stats:,}")
    n_scores = load_match_scores(
        conn, scores, match_map, opta_map, fotmob_map, team_map, season
    )
    print(f"  player_match_scores: {n_scores:,}")
    n_index = load_index(conn, ranking, opta_map, season)
    print(f"  season_index: {n_index:,}")
    load_trophies(conn, champions, detail, opta_map, team_map, season)
    return {
        "matches": len(match_map),
        "players": len(fotmob_map),
        "stats": n_stats,
        "scores": n_scores,
        "index": n_index,
    }


def _id_maps(conn) -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    opta: dict[str, int] = {}
    fotmob_players: dict[str, int] = {}
    matches: dict[str, int] = {}
    teams: dict[str, int] = {}
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT entity_type, source, external_key, entity_id
            FROM external_ids
            WHERE source IN ('fotmob', 'opta')
            """
        )
        for row in cur.fetchall():
            key = str(row["external_key"])
            eid = int(row["entity_id"])
            kind, source = row["entity_type"], row["source"]
            if kind == "player" and source == "opta":
                opta[key] = eid
            elif kind == "player" and source == "fotmob":
                fotmob_players[key] = eid
            elif kind == "match" and source == "fotmob":
                matches[key] = eid
            elif kind == "team" and source == "fotmob":
                teams[key] = eid
    return opta, fotmob_players, matches, teams


def reload_scores(conn, season: str, processed_dir) -> dict[str, int]:
    """Re-upsert match scores, index and trophies without touching raw stats."""
    tag = season.replace("/", "-")
    scores = pd.read_parquet(processed_dir / f"match_scores_{tag}.parquet")
    ranking = pd.read_parquet(processed_dir / f"ballondor_index_{tag}.parquet")
    ranking = ranking.rename(columns={"index": "index_value"})
    champions = pd.read_csv(processed_dir / f"champions_{tag}.csv")
    detail = pd.read_parquet(processed_dir / f"trophy_detail_{tag}.parquet")
    opta_map, fotmob_map, match_map, team_map = _id_maps(conn)
    n_scores = load_match_scores(
        conn, scores, match_map, opta_map, fotmob_map, team_map, season
    )
    n_index = load_index(conn, ranking, opta_map, season)
    load_trophies(conn, champions, detail, opta_map, team_map, season)
    return {"scores": n_scores, "index": n_index}

