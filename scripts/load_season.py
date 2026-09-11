"""Load FotMob parquet + scores for one season into Postgres.

    python scripts/load_season.py --season 2025/2026
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ballondor.db import connect, load_env
from ballondor.ingest.load_season import load_season, refresh_player_ages, reload_scores
import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", default="2025/2026")
    parser.add_argument(
        "--ages-only",
        action="store_true",
        help="Solo actualizar la edad de los jugadores ya cargados",
    )
    parser.add_argument(
        "--scores-only",
        action="store_true",
        help="Solo recargar match scores, índice y títulos",
    )
    args = parser.parse_args()
    load_env()
    tag = args.season.replace("/", "-")
    processed = ROOT / "data" / "processed"
    with connect() as conn:
        if args.ages_only:
            stats = pd.read_parquet(
                ROOT / "data" / "raw" / "fotmob" / f"player_match_stats_full_{tag}.parquet"
            )
            n = refresh_player_ages(conn, stats)
            conn.commit()
            print(f"edades actualizadas: {n:,}")
            return 0
        if args.scores_only:
            counts = reload_scores(conn, args.season, processed)
            conn.commit()
            print("recargado:", counts)
            return 0
        counts = load_season(
            conn,
            args.season,
            ROOT / "data" / "raw" / "fotmob",
            processed,
        )
        conn.commit()
    print("cargado:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
