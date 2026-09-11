"""Build the final Ballon d'Or index: performance + silverware.

    python scripts/build_index.py --season 2025/2026
    python scripts/build_index.py --trophy-weight 0.30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ballondor.scoring.match_score import ScoringConfig, season_score
from ballondor.scoring.trophies import IndexConfig, champions, season_index, trophy_points

RAW = ROOT / "data" / "raw" / "fotmob"
PROCESSED = ROOT / "data" / "processed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", default="2025/2026")
    parser.add_argument("--trophy-weight", type=float, default=0.18)
    parser.add_argument("--consistency-weight", type=float, default=0.10)
    parser.add_argument("--min-matches", type=int, default=15)
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument(
        "--balance-components",
        action="store_true",
        help="pesar por poder de discriminación en vez de por valor",
    )
    args = parser.parse_args()

    config = IndexConfig.load(
        individual_weight=1 - args.trophy_weight,
        trophy_weight=args.trophy_weight,
        consistency_weight=args.consistency_weight,
        min_matches=args.min_matches,
        balance_components=args.balance_components,
    )

    tag = args.season.replace("/", "-")
    matches = pd.read_parquet(RAW / f"matches_full_{tag}.parquet")
    scored = pd.read_parquet(PROCESSED / f"match_scores_{tag}.parquet")

    won = champions(matches)
    print(f"=== campeones deducidos de los datos ({len(won)}) ===")
    print(won[["competition_code", "winner", "runner_up", "decided_by"]].to_string(index=False))

    summary, detail = trophy_points(scored, won, config)
    print(f"\njugadores con palmarés: {len(summary):,}")

    ranking = season_score(scored, config=ScoringConfig.load())
    index = season_index(ranking, scored, summary, config)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    index.to_parquet(PROCESSED / f"ballondor_index_{tag}.parquet", index=False)
    index.to_csv(PROCESSED / f"ballondor_index_{tag}.csv", index=False)
    won.to_csv(PROCESSED / f"champions_{tag}.csv", index=False)
    # Un título por fila, para poder auditar de dónde sale cada punto.
    detail.to_parquet(PROCESSED / f"trophy_detail_{tag}.parquet", index=False)

    print(f"\n=== Índice Balón de Oro {args.season} "
          f"({config.individual_weight:.0%} rendimiento / {config.trophy_weight:.0%} títulos) ===")
    cols = ["rank", "player", "club", "position_group", "matches", "goals", "assists",
            "mean_rating", "individual_score", "trophies", "trophy_score", "index"]
    print(index.head(args.top)[cols].round(1).to_string(index=False))

    # El peso declarado y el peso que acaba teniendo no son lo mismo.
    top25 = index.head(25)
    hundred = index.head(100)
    value_share = (config.trophy_weight * top25.trophy_term / top25["index"]).mean()
    perf_var = (config.individual_weight * hundred.individual_score).std()
    trophy_var = (config.trophy_weight * hundred.trophy_term).std()
    print(f"\npalmarés: {value_share:.1%} del valor del índice en el top 25, "
          f"{trophy_var / (perf_var + trophy_var):.0%} de la varianza del top 100")
    print(f"jugadores elegibles (>={config.min_matches} partidos): {len(index):,}")

    print(f"\nescrito ballondor_index_{tag}.parquet y champions_{tag}.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
