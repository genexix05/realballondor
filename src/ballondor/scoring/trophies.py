"""Trophies won, and the season index that combines them with performance.

Champions are derived from the match data rather than typed in by hand. Cups
resolve through their final; leagues through the final table built from results.

Six of the seventeen 2025/26 finals ended level and went to penalties, the
Champions League final among them, so the scoreline alone cannot name a winner.
The shootout lives in ``matchFacts.events.penaltyShootoutEvents`` in the cached
payload. Its per-event running score is misleading -- the Champions League final
ends showing 5-4 when the real tally was 4-3 -- so the winner comes from
counting events of type ``Goal`` on each side.

Trophy credit is scaled by how much of the campaign a player actually played, so
a fringe squad member does not collect the same as the captain.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT / "data" / "cache" / "fotmob" / "matches"
CONFIG_DIR = ROOT / "config"

LEAGUE_CODES = {
    "ESP-La Liga", "ENG-Premier League", "GER-Bundesliga",
    "ITA-Serie A", "FRA-Ligue 1",
}


@dataclass
class IndexConfig:
    """How performance and silverware combine into the final index."""

    individual_weight: float = 0.82
    trophy_weight: float = 0.18
    consistency_weight: float = 0.10
    """How far regularity can move a total, as a fraction. 0 disables it."""

    min_matches: int = 15
    """Below this a season is too small a sample to rank."""

    balance_components: bool = False
    """Equalise how much each component spreads the leading players apart.

    Off by default because the declared weight is already honest as a share of
    the index: silverware supplies 15.6% of the value of a top-25 season, near
    the 18% asked for. It does however carry more *discriminating* power than
    that up at the top -- 32% of the variance of the leading hundred -- because
    performance compresses there while trophies still use the full range. Turn
    this on to weight by discriminating power instead of by value.
    """

    balance_pool: int = 100
    """How many leading players define 'the top' when balancing."""

    trophies: dict[str, dict[str, float]] | None = None

    @classmethod
    def load(cls, config_dir: Path | None = None, **overrides) -> IndexConfig:
        config_dir = config_dir or CONFIG_DIR
        data = yaml.safe_load((config_dir / "competitions.yml").read_text(encoding="utf-8"))
        return cls(trophies=data.get("trophies") or {}, **overrides)


# --------------------------------------------------------------------- #
# Who won what
# --------------------------------------------------------------------- #


def shootout_winner(match_id: str, cache_dir: Path | None = None) -> str | None:
    """``"home"``, ``"away"`` or ``None`` if the match had no shootout."""
    path = (cache_dir or CACHE_DIR) / f"{match_id}.json.gz"
    if not path.exists():
        return None
    props = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    events = ((props.get("content") or {}).get("matchFacts") or {}).get("events") or {}
    shootout = events.get("penaltyShootoutEvents") or []
    if not shootout:
        return None
    home = sum(1 for e in shootout if e.get("isHome") and e.get("type") == "Goal")
    away = sum(1 for e in shootout if not e.get("isHome") and e.get("type") == "Goal")
    if home == away:
        return None
    return "home" if home > away else "away"


def league_table(matches: pd.DataFrame) -> pd.DataFrame:
    """Final standings per league, from the results themselves."""
    leagues = matches[matches.competition_code.isin(LEAGUE_CODES)]
    home = leagues.rename(
        columns={"home_team_id": "team_id", "home_team": "team",
                 "home_score": "goals_for", "away_score": "goals_against"}
    )[["competition_code", "team_id", "team", "goals_for", "goals_against"]]
    away = leagues.rename(
        columns={"away_team_id": "team_id", "away_team": "team",
                 "away_score": "goals_for", "home_score": "goals_against"}
    )[["competition_code", "team_id", "team", "goals_for", "goals_against"]]

    long = pd.concat([home, away], ignore_index=True)
    long["points"] = (long.goals_for > long.goals_against) * 3 + (
        long.goals_for == long.goals_against
    ) * 1
    table = long.groupby(["competition_code", "team_id", "team"], as_index=False).agg(
        played=("points", "size"), points=("points", "sum"),
        goals_for=("goals_for", "sum"), goals_against=("goals_against", "sum")
    )
    table["goal_difference"] = table.goals_for - table.goals_against
    table = table.sort_values(
        ["competition_code", "points", "goal_difference", "goals_for"],
        ascending=[True, False, False, False],
    )
    table["position"] = table.groupby("competition_code").cumcount() + 1
    return table.reset_index(drop=True)


def champions(matches: pd.DataFrame, cache_dir: Path | None = None) -> pd.DataFrame:
    """Winner and runner-up of every competition in the dataset."""
    rows = []

    for row in matches[matches.stage == "final"].itertuples():
        home_id, away_id = str(row.home_team_id), str(row.away_team_id)
        if row.home_score > row.away_score:
            winner, loser, decided = (home_id, row.home_team), (away_id, row.away_team), "90"
        elif row.away_score > row.home_score:
            winner, loser, decided = (away_id, row.away_team), (home_id, row.home_team), "90"
        else:
            side = shootout_winner(str(row.fotmob_match_id), cache_dir)
            if side is None:
                continue
            home, away = (home_id, row.home_team), (away_id, row.away_team)
            winner, loser = (home, away) if side == "home" else (away, home)
            decided = "penaltis"
        rows.append({
            "competition_code": row.competition_code,
            "winner_id": winner[0], "winner": winner[1],
            "runner_up_id": loser[0], "runner_up": loser[1],
            "decided_by": decided,
        })

    table = league_table(matches)
    for code, group in table.groupby("competition_code"):
        top = group.nsmallest(2, "position")
        if len(top) < 2:
            continue
        first, second = top.iloc[0], top.iloc[1]
        rows.append({
            "competition_code": code,
            "winner_id": str(first.team_id), "winner": first.team,
            "runner_up_id": str(second.team_id), "runner_up": second.team,
            "decided_by": f"tabla ({first.points} pts)",
        })

    return pd.DataFrame(rows).sort_values("competition_code").reset_index(drop=True)


# --------------------------------------------------------------------- #
# Trophy credit per player
# --------------------------------------------------------------------- #


def participation(scored: pd.DataFrame) -> pd.DataFrame:
    """Share of a campaign each player actually contributed, per competition.

    Measured against the teammate in the same *position group* with the
    highest Match Score sum, not raw minutes. A rotation forward who plays
    fifty cameos should not collect more of the league title than the starter
    who missed two months but produced more when he played.
    """
    played = scored.groupby(
        ["competition_code", "team_id", "position_group", "opta_player_id"],
        as_index=False,
    ).agg(
        contribution=("match_score", "sum"),
        minutes=("minutes", "sum"),
        player=("player", "last"),
    )
    benchmark = played.groupby(
        ["competition_code", "team_id", "position_group"], as_index=False
    ).agg(squad_max=("contribution", "max"))
    out = played.merge(
        benchmark, on=["competition_code", "team_id", "position_group"]
    )
    out["share"] = (out.contribution / out.squad_max.replace(0, pd.NA)).fillna(0.0).clip(0, 1)
    return out


def trophy_points(
    scored: pd.DataFrame, won: pd.DataFrame, config: IndexConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Participation-weighted trophy score per player, and the breakdown."""
    weights = config.trophies or {}
    shares = participation(scored)
    rows = []

    for trophy in won.itertuples():
        weight = weights.get(trophy.competition_code)
        if not weight:
            continue
        for role, team_id, team in (
            ("winner", trophy.winner_id, trophy.winner),
            ("runner_up", trophy.runner_up_id, trophy.runner_up),
        ):
            value = weight.get(role, 0.0)
            if not value:
                continue
            squad = shares[
                (shares.competition_code == trophy.competition_code)
                & (shares.team_id == team_id)
            ]
            for player in squad.itertuples():
                rows.append({
                    "opta_player_id": player.opta_player_id,
                    "player": player.player,
                    "position_group": player.position_group,
                    "competition_code": trophy.competition_code,
                    "team": team,
                    "role": role,
                    "share": player.share,
                    "points": value * player.share,
                })

    detail = pd.DataFrame(rows)
    if detail.empty:
        empty = pd.DataFrame(columns=["opta_player_id", "trophy_points", "trophies"])
        return empty, detail

    summary = detail.groupby("opta_player_id", as_index=False).agg(
        trophy_points=("points", "sum"),
        trophies=("role", lambda r: int((r == "winner").sum())),
    )
    names = scored.groupby("opta_player_id")["player"].agg(
        lambda s: s.mode().iloc[0] if len(s.mode()) else s.iloc[-1]
    )
    detail = detail.drop(columns=["player"]).merge(
        names.rename("player"), on="opta_player_id", how="left"
    )
    return summary, detail


# --------------------------------------------------------------------- #
# Final index
# --------------------------------------------------------------------- #


def consistency(scored: pd.DataFrame, by: str = "opta_player_id") -> pd.DataFrame:
    """How evenly a player's Match Scores are spread.

    A season summed to the same total can come from steady contribution or from
    three explosions and a lot of silence; the sum cannot tell them apart.
    Expressed as ``1 - coefficient of variation``, so 1 is metronomic.
    """
    grouped = scored.groupby(by)["match_score"]
    stats = grouped.agg(["mean", "std"]).reset_index()
    stats["consistency"] = (1 - stats["std"] / stats["mean"].replace(0, pd.NA)).clip(0, 1)
    return stats[[by, "consistency"]].fillna({"consistency": 0.0})


def season_index(
    season_scores: pd.DataFrame,
    scored: pd.DataFrame,
    trophies: pd.DataFrame,
    config: IndexConfig,
) -> pd.DataFrame:
    """Blend performance and silverware into the published index.

    Availability is not a separate multiplier. Volume still counts through the
    sum half of the season score; the other half is the player's level, so a
    shorter excellent campaign is no longer buried by a long average one.
    """
    out = season_scores.merge(consistency(scored), on="opta_player_id", how="left")
    out = out.merge(trophies, on="opta_player_id", how="left")
    out["trophy_points"] = out.trophy_points.fillna(0.0)
    out["trophies"] = out.trophies.fillna(0).astype(int)

    eligible = out[out.matches >= config.min_matches].copy()
    typical = eligible.consistency.median()
    eligible["consistency_factor"] = 1 + config.consistency_weight * (
        eligible.consistency.fillna(typical) - typical
    )
    eligible["individual_raw"] = eligible.season_score * eligible.consistency_factor

    def to_100(values: pd.Series) -> pd.Series:
        top = values.max()
        return values / top * 100 if top else values * 0

    eligible["individual_score"] = to_100(eligible.individual_raw)
    eligible["trophy_score"] = to_100(eligible.trophy_points)

    trophy_term = eligible.trophy_score
    if config.balance_components:
        # Measured on the leading players, not the whole pool: three quarters of
        # eligible players won nothing, which shrinks the trophy spread and
        # would turn this into an amplifier instead of a brake.
        pool = eligible.nlargest(config.balance_pool, "individual_raw")
        trophy_spread = pool.trophy_score.std()
        if trophy_spread:
            # Zero stays zero: a player without silverware earns nothing here.
            trophy_term = trophy_term * (pool.individual_score.std() / trophy_spread)
    eligible["trophy_term"] = trophy_term
    eligible["index"] = (
        config.individual_weight * eligible.individual_score
        + config.trophy_weight * trophy_term
    )
    eligible = eligible.sort_values("index", ascending=False).reset_index(drop=True)
    eligible.insert(0, "rank", range(1, len(eligible) + 1))
    return eligible
