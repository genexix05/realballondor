#!/usr/bin/env python3
"""Build FBref player×match CSV using player match-logs (fast path).

Same strategy as worldfootballR::fb_player_match_logs, but by default scrapes
the FULL outfield pack (summary+passing+gca+defense+possession+misc) and merges
into one wide CSV — so Big 5 / next leagues start complete.

Examples:
  # Full pack (recommended default)
  python scripts/build_fbref_dataset.py --scope laliga --min-minutes 450

  # Smoke test
  python scripts/build_fbref_dataset.py --scope laliga --limit 2

  # Only one tab (legacy / debug)
  python scripts/build_fbref_dataset.py --stat-types summary
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ballondor.ingest.fbref_player_logs import (  # noqa: E402
    DEFAULT_STAT_TYPES,
    build_dataset,
)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--season-end-year", type=int, default=2026)
    p.add_argument("--scope", choices=["laliga", "big5"], default="laliga")
    p.add_argument(
        "--min-minutes",
        type=float,
        default=450,
        help="Skip players below this season minutes",
    )
    p.add_argument("--pause", type=float, default=2.5, help="Seconds between page loads")
    p.add_argument("--limit", type=int, default=None, help="Max players (smoke tests)")
    p.add_argument(
        "--stat-types",
        default=",".join(DEFAULT_STAT_TYPES),
        help=(
            "Comma-separated FBref tabs. Default = full pack: "
            + ",".join(DEFAULT_STAT_TYPES)
        ),
    )
    args = p.parse_args()
    stat_types = tuple(s.strip() for s in args.stat_types.split(",") if s.strip())

    out = build_dataset(
        season_end_year=args.season_end_year,
        scope=args.scope,
        min_minutes=args.min_minutes,
        pause=args.pause,
        limit=args.limit,
        stat_types=stat_types,
    )
    print(out)


if __name__ == "__main__":
    main()
