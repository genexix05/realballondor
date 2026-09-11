"""Ingest match results from football-data.co.uk."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
import requests
from psycopg.rows import dict_row

from ballondor.ingest.seed import get_competition_id

# Season code YYZZ -> football-data path mmz4281/YYZZ/SP1.csv
FD_BASE = "https://www.football-data.co.uk/mmz4281"


def season_to_fd_code(season: str) -> str:
    """Accept '2526' or '2025-2026' → '2526'."""
    season = season.strip()
    if len(season) == 4 and season.isdigit():
        return season
    if "-" in season:
        start, end = season.split("-", 1)
        return f"{start[-2:]}{end[-2:]}"
    raise ValueError(f"Unrecognized season format: {season}")


def season_label(season: str) -> str:
    code = season_to_fd_code(season)
    return f"20{code[:2]}-20{code[2:]}"


def fetch_laliga_results(season: str) -> pd.DataFrame:
    code = season_to_fd_code(season)
    url = f"{FD_BASE}/{code}/SP1.csv"
    resp = requests.get(url, timeout=60, allow_redirects=True)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.content.decode("utf-8-sig")))
    if df.empty:
        raise RuntimeError(f"Empty football-data file: {url}")
    return df


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


def _ensure_external(
    conn, entity_type: str, entity_id: int, source: str, external_key: str
) -> None:
    conn.execute(
        """
        INSERT INTO external_ids (entity_type, entity_id, source, external_key)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (entity_type, source, external_key) DO UPDATE
          SET entity_id = EXCLUDED.entity_id
        """,
        (entity_type, entity_id, source, external_key),
    )


def ingest_football_data_laliga(conn, season: str, competition_code: str = "ESP-La Liga") -> dict[str, Any]:
    df = fetch_laliga_results(season)
    competition_id = get_competition_id(conn, competition_code)
    label = season_label(season)
    upserted = 0

    for _, row in df.iterrows():
        home = str(row["HomeTeam"]).strip()
        away = str(row["AwayTeam"]).strip()
        if not home or not away or home == "nan":
            continue
        date = pd.to_datetime(row["Date"], dayfirst=True).date()
        home_id = _upsert_team(conn, home)
        away_id = _upsert_team(conn, away)
        home_score = int(row["FTHG"]) if pd.notna(row.get("FTHG")) else None
        away_score = int(row["FTAG"]) if pd.notna(row.get("FTAG")) else None

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
                    'football-data', %s
                )
                ON CONFLICT (competition_id, date, home_team_id, away_team_id) DO UPDATE SET
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    season = EXCLUDED.season,
                    source = EXCLUDED.source,
                    source_match_id = EXCLUDED.source_match_id
                RETURNING match_id
                """,
                (
                    date,
                    label,
                    competition_id,
                    home_id,
                    away_id,
                    home_score,
                    away_score,
                    f"SP1:{date}:{home}:{away}",
                ),
            )
            match_id = int(cur.fetchone()["match_id"])
        upserted += 1
        _ensure_external(conn, "match", match_id, "football-data", f"SP1:{date}:{home}:{away}")

    return {"matches_upserted": upserted, "season": label, "rows_in_file": len(df)}
