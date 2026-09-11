"""Seed competitions from config/competitions.yml."""

from __future__ import annotations

from pathlib import Path

import yaml
from psycopg.rows import dict_row

from ballondor.db import connect

ROOT = Path(__file__).resolve().parents[3]


def seed_competitions(conn) -> int:
    path = ROOT / "config" / "competitions.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = data.get("competitions", [])
    upserted = 0
    for row in rows:
        conn.execute(
            """
            INSERT INTO competitions (code, name, type, country, weight)
            VALUES (%(code)s, %(name)s, %(type)s, %(country)s, %(weight)s)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                type = EXCLUDED.type,
                country = EXCLUDED.country,
                weight = EXCLUDED.weight
            """,
            row,
        )
        upserted += 1
    return upserted


def get_competition_id(conn, code: str) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT competition_id FROM competitions WHERE code = %s", (code,))
        row = cur.fetchone()
        if not row:
            raise KeyError(f"Competition not found: {code}")
        return int(row["competition_id"])


if __name__ == "__main__":
    with connect() as conn:
        n = seed_competitions(conn)
        conn.commit()
        print(f"Seeded {n} competitions")
