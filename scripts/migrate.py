#!/usr/bin/env python3
"""Apply SQL migrations in db/migrations/ in lexical order."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ballondor.db import connect, load_env  # noqa: E402


def main() -> None:
    load_env()
    migrations_dir = ROOT / "db" / "migrations"
    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        print("No migrations found.")
        return

    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied = {
            row[0]
            for row in conn.execute("SELECT filename FROM schema_migrations").fetchall()
        }
        for path in files:
            if path.name in applied:
                print(f"skip {path.name}")
                continue
            sql = path.read_text(encoding="utf-8")
            print(f"apply {path.name} ...")
            with conn.transaction():
                conn.execute(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (path.name,),
                )
            print(f"ok   {path.name}")
    print("Migrations complete.")


if __name__ == "__main__":
    main()
