#!/usr/bin/env python3
"""Pilot ingest: La Liga results (football-data) + FBref player match logs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ballondor.db import connect, load_env  # noqa: E402
from ballondor.ingest.fbref import ingest_fbref_laliga  # noqa: E402
from ballondor.ingest.football_data import ingest_football_data_laliga  # noqa: E402
from ballondor.ingest.seed import seed_competitions  # noqa: E402


def main() -> None:
    load_env()
    league = os.getenv("PILOT_LEAGUE", "ESP-La Liga")
    season = os.getenv("PILOT_SEASON", "2526")

    with connect() as conn:
        run = conn.execute(
            """
            INSERT INTO ingest_runs (source, league, season, status, meta)
            VALUES ('pilot', %s, %s, 'running', %s::jsonb)
            RETURNING ingest_run_id
            """,
            (league, season, json.dumps({"steps": ["seed", "football-data", "fbref"]})),
        ).fetchone()
        run_id = int(run[0])
        conn.commit()

        try:
            seeded = seed_competitions(conn)
            fd_stats = ingest_football_data_laliga(conn, season=season, competition_code=league)
            conn.commit()
            print("football-data:", fd_stats)

            fb_stats = ingest_fbref_laliga(conn, league=league, season=season, competition_code=league)
            conn.commit()
            print("fbref:", fb_stats)

            total = fd_stats["matches_upserted"] + fb_stats["player_match_stats_upserted"]
            conn.execute(
                """
                UPDATE ingest_runs
                SET status = 'success',
                    finished_at = now(),
                    rows_upserted = %s,
                    meta = %s::jsonb
                WHERE ingest_run_id = %s
                """,
                (
                    total,
                    json.dumps({"seeded_competitions": seeded, "football_data": fd_stats, "fbref": fb_stats}),
                    run_id,
                ),
            )
            conn.commit()
            print(f"Pilot run {run_id} complete. rows_upserted={total}")
        except Exception as exc:  # noqa: BLE001
            conn.execute(
                """
                UPDATE ingest_runs
                SET status = 'failed', finished_at = now(), error_message = %s
                WHERE ingest_run_id = %s
                """,
                (str(exc), run_id),
            )
            conn.commit()
            raise


if __name__ == "__main__":
    main()
