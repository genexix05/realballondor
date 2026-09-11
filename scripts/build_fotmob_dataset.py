"""Build the player x match dataset from FotMob.

Seasons are always given as our own August-July window ("2025/2026"), including
for one-off tournaments: the 2026 World Cup and the January 2026 Supercopa both
belong to 2025/2026. FotMob's own labels are inconsistent, so matches are
selected by kickoff date instead.

Examples:
    python scripts/build_fotmob_dataset.py --league laliga --season 2025/2026 --limit 5
    python scripts/build_fotmob_dataset.py --scope full --season 2025/2026
    python scripts/build_fotmob_dataset.py --scope cups --season 2025/2026
    python scripts/build_fotmob_dataset.py --league champions-league --list-seasons
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ballondor.ingest.fotmob import LEAGUES, FotMobClient, iter_season

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "fotmob"

BIG5 = ["laliga", "premier-league", "bundesliga", "serie-a", "ligue-1"]
CUPS = ["copa-del-rey", "fa-cup", "efl-cup", "dfb-pokal", "coppa-italia", "coupe-de-france"]
SUPER_CUPS = ["supercopa", "community-shield", "dfl-supercup", "supercoppa-italiana",
              "trophee-des-champions", "uefa-super-cup"]
EUROPE = ["champions-league", "europa-league", "conference-league"]
INTERCONTINENTAL = ["intercontinental-cup", "club-world-cup"]

SCOPES = {
    "big5": BIG5,
    "cups": CUPS,
    "super-cups": SUPER_CUPS,
    "europe": EUROPE,
    "intercontinental": INTERCONTINENTAL,
    "mvp": BIG5 + ["champions-league"],
    "full": BIG5 + EUROPE + CUPS + SUPER_CUPS + INTERCONTINENTAL + ["world-cup"],
    "all": list(LEAGUES),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--league", action="append", choices=sorted(LEAGUES),
                   help="Competition key; repeatable.")
    p.add_argument("--scope", choices=sorted(SCOPES), help="Preset group of competitions.")
    p.add_argument("--season", default="2025/2026",
                   help="Our August-July season window, e.g. 2025/2026.")
    p.add_argument("--limit", type=int, help="Only the first N matches per competition (smoke test).")
    p.add_argument("--delay", type=float, default=0.6, help="Seconds between requests.")
    p.add_argument("--list-seasons", action="store_true", help="Print available seasons and exit.")
    p.add_argument("--tag", help="Suffix for the output filenames.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    keys = args.league or SCOPES.get(args.scope or "", [])
    if not keys:
        print("Pick at least one --league or a --scope.", file=sys.stderr)
        return 2

    client = FotMobClient(delay=args.delay)

    if args.list_seasons:
        for key in keys:
            print(f"{key}: {', '.join(client.available_seasons(LEAGUES[key]))}")
        return 0

    all_matches: list[dict] = []
    all_players: list[dict] = []

    for key in keys:
        league = LEAGUES[key]
        print(f"\n=== {key} ({league.code}) {args.season} ===")

        def progress(i, total, fixture, n_players, error):
            label = f"{fixture['home']['name']} vs {fixture['away']['name']}"
            if error:
                print(f"  [{i}/{total}] {label:<48} FAILED: {type(error).__name__}: {error}")
            else:
                cached = "" if n_players else " (empty)"
                print(f"  [{i}/{total}] {label:<48} {n_players:>2} players{cached}")

        try:
            for match, players in iter_season(client, league, args.season,
                                              limit=args.limit, on_progress=progress):
                all_matches.append(match)
                all_players.extend(players)
        except Exception as exc:  # noqa: BLE001
            print(f"  competition failed: {type(exc).__name__}: {exc}", file=sys.stderr)

    if not all_players:
        print("\nNo rows produced.", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tag = args.tag or (args.scope or "-".join(keys))
    season_tag = args.season.replace("/", "-")

    matches_df = pd.DataFrame(all_matches)
    players_df = pd.DataFrame(all_players)

    for name, df in (("matches", matches_df), ("player_match_stats", players_df)):
        base = OUT_DIR / f"{name}_{tag}_{season_tag}"
        df.to_parquet(base.with_suffix(".parquet"), index=False)
        df.to_csv(base.with_suffix(".csv"), index=False, encoding="utf-8")
        print(f"\n{name}: {len(df):,} rows x {len(df.columns)} cols -> {base}.parquet/.csv")

    coverage = players_df["rating"].notna().mean() if "rating" in players_df else 0
    print(f"rating coverage: {coverage:.1%}")
    print(f"distinct players: {players_df['fotmob_player_id'].nunique():,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
