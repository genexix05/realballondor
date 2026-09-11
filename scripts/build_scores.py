"""Compute Match Scores and the season ranking for one season.

    python scripts/build_scores.py --season 2025/2026
    python scripts/build_scores.py --minutes-damping 0.5   # castiga cameos
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ballondor.scoring.match_score import (
    ScoringConfig,
    add_derived,
    apply_context,
    base_performance,
    fill_structural_zeros,
    reference_levels,
    season_score,
)

RAW = ROOT / "data" / "raw" / "fotmob"
PROCESSED = ROOT / "data" / "processed"


def load(season: str) -> pd.DataFrame:
    tag = season.replace("/", "-")
    stats = pd.read_parquet(RAW / f"player_match_stats_full_{tag}.parquet")
    matches = pd.read_parquet(RAW / f"matches_full_{tag}.parquet").rename(
        columns={"fotmob_match_id": "match_id"}
    )
    strength = pd.read_parquet(PROCESSED / f"opponent_strength_{tag}.parquet")

    stats["match_id"] = stats.fotmob_match_id.astype(str)
    stats["team_id"] = stats.fotmob_team_id.astype(str)
    matches["match_id"] = matches.match_id.astype(str)

    stats = stats.drop(
        columns=[c for c in ("competition_code", "season", "stage") if c in stats]
    )
    stats = stats.merge(
        matches[["match_id", "competition_code", "stage", "coverage_level", "kickoff_utc"]],
        on="match_id",
        how="left",
    )
    return stats.merge(
        strength[["match_id", "team_id", "opponent", "opponent_strength", "team_strength"]],
        on=["match_id", "team_id"],
        how="left",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", default="2025/2026")
    parser.add_argument("--minutes-damping", type=float, default=0.0)
    parser.add_argument("--rating-weight", type=float, default=None)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    config = ScoringConfig.load(minutes_damping=args.minutes_damping)
    if args.rating_weight is not None:
        config.rating["weight"] = args.rating_weight

    stats = load(args.season)
    print(f"filas jugador×partido: {len(stats):,}")
    missing = stats.opponent_strength.isna().sum()
    print(f"  sin fuerza de rival: {missing}")

    stats = add_derived(stats)
    stats = fill_structural_zeros(stats, sorted(config.all_stats))
    references = reference_levels(stats, config)
    print(f"\nreferencias (percentil {config.reference_quantile:.0%}) por posición:")
    pivot = references.pivot(index="stat", columns="position_group", values="reference")
    print(pivot.round(2).to_string())

    scored = base_performance(stats, config, references)
    scored = apply_context(scored, config)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    tag = args.season.replace("/", "-")
    keep = [
        "match_id", "opta_player_id", "player", "team", "team_id", "opponent",
        "position_group", "competition_code", "stage", "kickoff_utc", "minutes",
        "rating", "goals", "assists", "coverage_level", "stats_score", "rating_score",
        "penalty_score", "performance", "reliability", "opponent_strength",
        "opponent_multiplier", "competition_weight", "stage_weight", "match_score",
    ]
    out = scored[[c for c in keep if c in scored.columns]]
    out.to_parquet(PROCESSED / f"match_scores_{tag}.parquet", index=False)

    ranking = season_score(scored, config=config)
    ranking.insert(0, "rank", range(1, len(ranking) + 1))
    ranking.to_parquet(PROCESSED / f"season_scores_{tag}.parquet", index=False)
    ranking.to_csv(PROCESSED / f"season_scores_{tag}.csv", index=False)

    print(f"\n=== Top {args.top} — damping={config.minutes_damping} "
          f"rating_weight={config.rating['weight']} ===")
    cols = ["rank", "player", "club", "position_group", "matches", "minutes",
            "goals", "assists", "mean_rating", "mean_match_score", "season_score"]
    print(ranking.head(args.top)[cols].round(2).to_string(index=False))
    print(f"\nescrito match_scores_{tag}.parquet y season_scores_{tag}.parquet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
