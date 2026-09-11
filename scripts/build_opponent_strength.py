"""Build the opponent-strength table for a season, as of each kickoff.

Clubs are rated from the UEFA five-year coefficient blended with league form
scaled by the country coefficient; national teams from the FIFA ranking edition
in force at kickoff. Every input is read as of the match, never after it.

    python scripts/build_opponent_strength.py --season 2025/2026
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ballondor.ingest.fotmob import (
    LEAGUES,
    FotMobClient,
    season_window,
)
from ballondor.ingest.rankings import (
    fifa_rankings_covering,
    uefa_club_coefficients,
)
from ballondor.scoring.strength import (
    StrengthConfig,
    ambiguous_club_keys,
    attach_uefa,
    blend,
    domestic_strength,
    normalise_nation,
)

BIG5 = ["laliga", "premier-league", "bundesliga", "serie-a", "ligue-1"]
OUT_DIR = ROOT / "data" / "processed"


def previous_season(season: str) -> str:
    start = int(season.split("/")[0])
    return f"{start - 1}/{start}"


def league_results(client: FotMobClient, season: str) -> pd.DataFrame:
    rows = []
    for key in BIG5:
        league = LEAGUES[key]
        got = client.season_results(league, season)
        print(f"  {league.code:<22} {season}  {len(got):>4} resultados")
        rows.extend(got)
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", default="2025/2026")
    parser.add_argument("--matches", type=Path, default=None)
    parser.add_argument("--uefa-weight", type=float, default=0.35)
    parser.add_argument("--prior-matches", type=float, default=8.0)
    parser.add_argument("--league-exponent", type=float, default=0.5)
    args = parser.parse_args()

    config = StrengthConfig(
        prior_matches=args.prior_matches,
        league_exponent=args.league_exponent,
        uefa_weight=args.uefa_weight,
    )
    tag = args.season.replace("/", "-")
    matches_path = args.matches or ROOT / "data" / "raw" / "fotmob" / f"matches_full_{tag}.parquet"
    matches = pd.read_parquet(matches_path).rename(columns={"fotmob_match_id": "match_id"})
    matches["match_id"] = matches.match_id.astype(str)
    matches["kickoff"] = (
        pd.to_datetime(matches["kickoff_utc"], utc=True).dt.tz_localize(None)
    ).astype("datetime64[ns]")
    print(f"partidos: {len(matches):,} de {matches_path.name}")

    client = FotMobClient()
    print("\nresultados de liga (temporada previa, línea base):")
    previous = league_results(client, previous_season(args.season))
    print("resultados de liga (temporada actual, forma):")
    current = league_results(client, args.season)

    print("\ncoeficientes UEFA…")
    uefa = uefa_club_coefficients(args.season)
    print(f"  {len(uefa)} clubes, ventana {uefa.window.iloc[0]}")

    # ---- one query row per side of every match ----
    sides = pd.concat(
        [
            matches.assign(team_id=matches.home_team_id, team=matches.home_team,
                           opponent_id=matches.away_team_id, opponent=matches.away_team,
                           side="home"),
            matches.assign(team_id=matches.away_team_id, team=matches.away_team,
                           opponent_id=matches.home_team_id, opponent=matches.home_team,
                           side="away"),
        ],
        ignore_index=True,
    )[["match_id", "competition_code", "kickoff", "team_id", "team",
       "opponent_id", "opponent", "side"]]
    sides["team_id"] = sides.team_id.astype(str)
    sides["opponent_id"] = sides.opponent_id.astype(str)

    national = sides.competition_code.isin(
        {"INT-World Cup", "INT-Euro", "INT-Copa America"}
    )
    clubs, nations = sides[~national].copy(), sides[national].copy()

    # ---- clubs ----
    print(f"\nfuerza de clubes ({len(clubs):,} lados)…")
    dom = domestic_strength(
        current=current,
        previous=previous,
        queries=clubs[["match_id", "team_id", "team", "kickoff", "side"]],
        country_coefficients=uefa[["country", "country_coefficient"]],
        config=config,
    )
    dom = attach_uefa(dom, uefa, config)
    dom = blend(dom, config)

    collisions = ambiguous_club_keys(uefa, config)
    if len(collisions):
        pairs = collisions.groupby("join_key")["club"].apply(list).head(6).to_dict()
        print(f"  nombres UEFA ambiguos: {len(collisions)} filas -> {pairs}")
    in_big5 = dom.home_league.notna()
    matched = dom[in_big5].drop_duplicates("team_id")
    print(f"  clubes Big 5: {len(matched)} | con coeficiente UEFA: "
          f"{int(matched.uefa_matched.sum())}")
    unmatched = sorted(matched.loc[~matched.uefa_matched, "team"].tolist())
    print(f"  sin coeficiente (no jugaron Europa en {uefa.window.iloc[0]}): {unmatched}")

    club_out = clubs.merge(
        dom[["match_id", "team_id", "side", "baseline_ppg", "cum_played", "blended_ppg",
             "league_factor", "domestic_score", "uefa_coefficient", "uefa_rank",
             "uefa_matched", "uefa_score", "opponent_strength"]],
        on=["match_id", "team_id", "side"],
        how="left",
    )

    # ---- national teams ----
    print(f"fuerza de selecciones ({len(nations):,} lados)…")
    if len(nations):
        start, end = season_window(args.season)
        fifa = fifa_rankings_covering(start, end)
        fifa["ranking_date"] = pd.to_datetime(fifa["ranking_date"]).astype("datetime64[ns]")
        fifa["join_key"] = fifa.team.map(normalise_nation)
        nations["join_key"] = nations.team.map(normalise_nation)
        nations = pd.merge_asof(
            nations.sort_values("kickoff"),
            fifa.sort_values("ranking_date")[
                ["join_key", "ranking_date", "rank", "points"]
            ].rename(columns={"rank": "fifa_rank", "points": "fifa_points"}),
            left_on="kickoff",
            right_on="ranking_date",
            by="join_key",
            direction="backward",
        )
        # Scaled against the whole ranking, not just the tournament field.
        # Dividing by the leader alone would floor the weakest World Cup side
        # at 0.64 and make it look tougher than a mid-table Liga club, because
        # FIFA points start around 750 rather than at zero.
        floor, ceiling = fifa.points.min(), fifa.points.max()
        nations["opponent_strength"] = (
            (nations.fifa_points - floor) / (ceiling - floor)
        ).clip(0, 1)
        missing = nations.fifa_rank.isna().sum()
        if missing:
            print(f"  aviso: {missing} lados sin ranking FIFA "
                  f"({sorted(nations[nations.fifa_rank.isna()].team.unique())[:8]})")

    out = pd.concat([club_out, nations], ignore_index=True)

    # What each component produced is the team's *own* strength; the opponent
    # multiplier is the other side's value on the same match.
    out = out.rename(columns={"opponent_strength": "team_strength"})
    other = out[["match_id", "team_id", "team_strength"]].rename(
        columns={"team_id": "opponent_id", "team_strength": "opponent_strength"}
    )
    out = out.merge(other, on=["match_id", "opponent_id"], how="left")
    out["season"] = args.season
    out["is_national"] = out.competition_code.isin(
        {"INT-World Cup", "INT-Euro", "INT-Copa America"}
    )
    out["uefa_matched"] = out.uefa_matched.fillna(False).astype(bool)
    out = out.drop(columns=[c for c in ("join_key", "ranking_date") if c in out])

    unresolved = out.opponent_strength.isna().sum()
    print(f"  lados sin fuerza de rival: {unresolved}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = OUT_DIR / f"opponent_strength_{tag}"
    out.to_parquet(f"{stem}.parquet", index=False)
    out.to_csv(f"{stem}.csv", index=False)
    print(f"\nescrito {stem}.parquet  ({len(out):,} filas x {out.shape[1]} cols)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
