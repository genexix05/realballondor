"""Ingest player match stats from FBref via soccerdata."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
from psycopg.rows import dict_row

from ballondor.ingest.football_data import season_label
from ballondor.ingest.seed import get_competition_id


def _norm_team(name: str) -> str:
    aliases = {
        "Athletic Club": "Ath Bilbao",
        "Atlético Madrid": "Ath Madrid",
        "Atletico Madrid": "Ath Madrid",
        "Celta Vigo": "Celta",
        "Deportivo Alavés": "Alaves",
        "Deportivo Alaves": "Alaves",
        "Rayo Vallecano": "Vallecano",
        "Real Betis": "Betis",
        "Real Sociedad": "Sociedad",
        "Real Oviedo": "Oviedo",
        "Espanyol": "Espanol",
        "Leganés": "Leganes",
        "Leganes": "Leganes",
    }
    name = name.strip()
    return aliases.get(name, name)


def _to_int(val) -> int | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _to_float(val) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _col(row: pd.Series, *names: str):
    for name in names:
        if name in row.index and pd.notna(row[name]):
            return row[name]
        # soccerdata sometimes uses MultiIndex flattened as 'stat_level'
        for idx in row.index:
            if str(idx).lower() == name.lower():
                return row[idx]
            if isinstance(idx, tuple) and any(str(p).lower() == name.lower() for p in idx):
                return row[idx]
    return None


def _upsert_team(conn, name: str, country: str = "ESP") -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO teams (name, country, type)
            VALUES (%s, %s, 'club')
            ON CONFLICT (name, type) DO UPDATE SET country = COALESCE(EXCLUDED.country, teams.country)
            RETURNING team_id
            """,
            (name, country),
        )
        return int(cur.fetchone()["team_id"])


def _upsert_player(conn, name: str, nationality: str | None, position: str | None) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT player_id FROM players WHERE name = %s
            ORDER BY player_id LIMIT 1
            """,
            (name,),
        )
        existing = cur.fetchone()
        if existing:
            pid = int(existing["player_id"])
            cur.execute(
                """
                UPDATE players
                SET nationality = COALESCE(%s, nationality),
                    primary_position = COALESCE(%s, primary_position)
                WHERE player_id = %s
                """,
                (nationality, position, pid),
            )
            return pid
        cur.execute(
            """
            INSERT INTO players (name, nationality, primary_position)
            VALUES (%s, %s, %s)
            RETURNING player_id
            """,
            (name, nationality, position),
        )
        return int(cur.fetchone()["player_id"])


def _find_match_id(
    conn,
    competition_id: int,
    date,
    team_name: str,
    opponent_name: str,
    venue: str | None,
) -> int | None:
    """Best-effort match to football-data rows by date + team names."""
    team_n = _norm_team(team_name)
    opp_n = _norm_team(opponent_name)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT m.match_id, ht.name AS home, at.name AS away
            FROM matches m
            JOIN teams ht ON ht.team_id = m.home_team_id
            JOIN teams at ON at.team_id = m.away_team_id
            WHERE m.competition_id = %s AND m.date = %s
            """,
            (competition_id, date),
        )
        candidates = cur.fetchall()
    for c in candidates:
        home, away = c["home"], c["away"]
        if venue and str(venue).lower().startswith("home"):
            if _norm_team(home) == team_n and _norm_team(away) == opp_n:
                return int(c["match_id"])
        if venue and str(venue).lower().startswith("away"):
            if _norm_team(away) == team_n and _norm_team(home) == opp_n:
                return int(c["match_id"])
        # Fallback: either ordering
        names = {_norm_team(home), _norm_team(away)}
        if {_norm_team(team_n), _norm_team(opp_n)} <= names or {team_n, opp_n} <= {home, away}:
            return int(c["match_id"])
    return None


def _ensure_match(
    conn,
    competition_id: int,
    season: str,
    date,
    team_name: str,
    opponent_name: str,
    venue: str | None,
    score_text: str | None,
) -> int:
    existing = _find_match_id(conn, competition_id, date, team_name, opponent_name, venue)
    if existing:
        return existing

    is_home = not (venue and str(venue).lower().startswith("away"))
    home_name = team_name if is_home else opponent_name
    away_name = opponent_name if is_home else team_name
    home_id = _upsert_team(conn, home_name)
    away_id = _upsert_team(conn, away_name)

    home_score = away_score = None
    if score_text and isinstance(score_text, str) and re.search(r"\d+\s*[-–]\s*\d+", score_text):
        a, b = re.split(r"[-–]", score_text.strip(), maxsplit=1)
        # FBref score is usually from perspective of the logged team when venue known
        try:
            left, right = int(a.strip()), int(b.strip())
            if is_home:
                home_score, away_score = left, right
            else:
                home_score, away_score = right, left
        except ValueError:
            pass

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO matches (
                date, season, competition_id, stage,
                home_team_id, away_team_id, home_score, away_score,
                source, source_match_id
            ) VALUES (
                %s, %s, %s, 'regular_season',
                %s, %s, %s, %s,
                'fbref', %s
            )
            ON CONFLICT (competition_id, date, home_team_id, away_team_id) DO UPDATE SET
                home_score = COALESCE(EXCLUDED.home_score, matches.home_score),
                away_score = COALESCE(EXCLUDED.away_score, matches.away_score)
            RETURNING match_id
            """,
            (
                date,
                season_label(season),
                competition_id,
                home_id,
                away_id,
                home_score,
                away_score,
                f"fbref:{date}:{home_name}:{away_name}",
            ),
        )
        return int(cur.fetchone()["match_id"])


def fetch_fbref_player_match_stats(league: str, season: str) -> pd.DataFrame:
    import soccerdata as sd

    fbref = sd.FBref(leagues=league, seasons=season)
    return fbref.read_player_match_stats(stat_type="summary")


def ingest_fbref_laliga(
    conn,
    league: str = "ESP-La Liga",
    season: str = "2526",
    competition_code: str = "ESP-La Liga",
) -> dict[str, Any]:
    df = fetch_fbref_player_match_stats(league, season)
    if df is None or df.empty:
        raise RuntimeError("FBref returned no player match stats")

    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            "_".join(str(p) for p in col if p and str(p) != "nan").strip("_")
            for col in df.columns
        ]

    df = df.reset_index()
    competition_id = get_competition_id(conn, competition_code)
    upserted = 0
    unmatched_matches = 0

    for _, row in df.iterrows():
        player_name = str(_col(row, "player", "Player") or "").strip()
        if not player_name or player_name.lower() == "nan":
            continue

        team_name = str(_col(row, "team", "Team", "squad", "Squad") or "").strip()
        opponent = str(_col(row, "opponent", "Opponent") or "").strip()
        date_raw = _col(row, "date", "Date")
        if not team_name or date_raw is None:
            continue
        date = pd.to_datetime(date_raw).date()
        venue = _col(row, "venue", "Venue")
        score = _col(row, "score", "Score", "result", "Result")

        match_id = _ensure_match(
            conn, competition_id, season, date, team_name, opponent, venue, str(score) if score else None
        )
        if match_id is None:
            unmatched_matches += 1
            continue

        nationality = _col(row, "nation", "Nation", "nationality")
        nationality = str(nationality).strip() if nationality is not None and str(nationality) != "nan" else None
        position = _col(row, "pos", "Pos", "position", "Position")
        position = str(position).strip() if position is not None and str(position) != "nan" else None

        player_id = _upsert_player(conn, player_name, nationality, position)
        team_id = _upsert_team(conn, team_name)

        minutes = _to_float(_col(row, "Min", "minutes", "Playing Time_Min", "summary_Min"))
        goals = _to_int(_col(row, "Gls", "goals", "Performance_Gls"))
        assists = _to_int(_col(row, "Ast", "assists", "Performance_Ast"))
        shots = _to_int(_col(row, "Sh", "shots", "Performance_Sh"))
        sot = _to_int(_col(row, "SoT", "shots_on_target", "Performance_SoT"))
        xg = _to_float(_col(row, "xG", "xg", "Expected_xG"))
        xa = _to_float(_col(row, "xAG", "xA", "xa", "Expected_xAG", "Expected_xA"))
        sca = _to_int(_col(row, "SCA", "Performance_SCA"))
        gca = _to_int(_col(row, "GCA", "Performance_GCA"))
        passes = _to_int(_col(row, "Cmp", "passes_completed", "Passes_Cmp"))
        passes_att = _to_int(_col(row, "Att", "passes", "Passes_Att"))
        key_passes = _to_int(_col(row, "KP", "key_passes"))
        prog_passes = _to_int(_col(row, "PrgP", "progressive_passes", "Passes_PrgP"))
        prog_carries = _to_int(_col(row, "PrgC", "progressive_carries", "Carries_PrgC"))
        tackles = _to_int(_col(row, "Tkl", "tackles", "Performance_Tkl"))
        interceptions = _to_int(_col(row, "Int", "interceptions", "Performance_Int"))
        blocks = _to_int(_col(row, "Blocks", "blocks", "Performance_Blocks"))
        yellow = _to_int(_col(row, "CrdY", "yellow_cards", "Performance_CrdY"))
        red = _to_int(_col(row, "CrdR", "red_cards", "Performance_CrdR"))

        started = None
        if minutes is not None:
            started = minutes >= 45

        conn.execute(
            """
            INSERT INTO player_match_stats (
                match_id, player_id, team_id,
                minutes, started, position,
                goals, assists, shots, shots_on_target, xg, xa,
                passes, passes_completed, key_passes,
                progressive_passes, progressive_carries,
                tackles, interceptions, blocks,
                yellow_cards, red_cards,
                source, raw
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                'fbref', %s::jsonb
            )
            ON CONFLICT (match_id, player_id) DO UPDATE SET
                team_id = EXCLUDED.team_id,
                minutes = EXCLUDED.minutes,
                started = EXCLUDED.started,
                position = EXCLUDED.position,
                goals = EXCLUDED.goals,
                assists = EXCLUDED.assists,
                shots = EXCLUDED.shots,
                shots_on_target = EXCLUDED.shots_on_target,
                xg = EXCLUDED.xg,
                xa = EXCLUDED.xa,
                passes = EXCLUDED.passes,
                passes_completed = EXCLUDED.passes_completed,
                key_passes = EXCLUDED.key_passes,
                progressive_passes = EXCLUDED.progressive_passes,
                progressive_carries = EXCLUDED.progressive_carries,
                tackles = EXCLUDED.tackles,
                interceptions = EXCLUDED.interceptions,
                blocks = EXCLUDED.blocks,
                yellow_cards = EXCLUDED.yellow_cards,
                red_cards = EXCLUDED.red_cards,
                source = EXCLUDED.source,
                raw = EXCLUDED.raw
            """,
            (
                match_id,
                player_id,
                team_id,
                minutes,
                started,
                position,
                goals,
                assists,
                shots,
                sot,
                xg,
                xa,
                passes_att,
                passes,
                key_passes,
                prog_passes,
                prog_carries,
                tackles,
                interceptions,
                blocks,
                yellow,
                red,
                pd.Series(row).astype(str).to_json(),
            ),
        )
        upserted += 1
        # silence unused vars for optional SCA/GCA until schema expands
        _ = (sca, gca)

    return {
        "player_match_stats_upserted": upserted,
        "rows_in_source": len(df),
        "unmatched_match_lookups": unmatched_matches,
        "season": season_label(season),
    }
