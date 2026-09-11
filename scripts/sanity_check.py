#!/usr/bin/env python3
"""Sanity-check queries after the La Liga pilot ingest."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ballondor.db import connect, load_env  # noqa: E402


QUERIES = [
    ("competitions", "SELECT count(*) FROM competitions"),
    ("teams", "SELECT count(*) FROM teams"),
    ("players", "SELECT count(*) FROM players"),
    ("matches", "SELECT count(*) FROM matches"),
    ("player_match_stats", "SELECT count(*) FROM player_match_stats"),
    (
        "matches_with_scores",
        "SELECT count(*) FROM matches WHERE home_score IS NOT NULL",
    ),
    (
        "pms_with_minutes",
        "SELECT count(*) FROM player_match_stats WHERE minutes IS NOT NULL AND minutes > 0",
    ),
    (
        "top_scorers_sample",
        """
        SELECT p.name, sum(s.goals) AS goals, count(*) AS apps, round(sum(s.minutes)::numeric,0) AS mins
        FROM player_match_stats s
        JOIN players p ON p.player_id = s.player_id
        WHERE s.goals IS NOT NULL
        GROUP BY p.name
        ORDER BY goals DESC NULLS LAST, mins DESC
        LIMIT 10
        """,
    ),
]


def main() -> None:
    load_env()
    with connect() as conn:
        for label, sql in QUERIES:
            rows = conn.execute(sql).fetchall()
            print(f"\n== {label} ==")
            for row in rows:
                print(row)


if __name__ == "__main__":
    main()
