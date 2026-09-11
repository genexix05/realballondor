"""Match Score: how good a performance was, in the context it happened in.

    Match Score = Performance x Reliability x Opponent x Competition x Stage

**Performance** mixes absolute contributions with the FotMob rating. Absolute,
not per 90: a player who was on the pitch for 90 minutes accumulates more
chances to contribute, so minutes are already inside the counts. Normalising to
90 and then damping by ``sqrt(minutes/90)`` looks like a penalty for cameos but
composes into ``stat x sqrt(90/minutes)``, which makes a goal in 30 minutes
worth 1.73 goals and one in 5 minutes worth 4.24. The counts are left alone.

Each statistic is divided by its 95th percentile within the position group
rather than z-scored. A z-score would hand every substitute a large negative
value on every count, which is a minutes penalty smuggled in through the back
door; dividing keeps zero at zero, so a quiet cameo scores near nothing instead
of scoring badly.

**Reliability** is the only place minutes appear explicitly, as ``(minutes/90)
** damping``. At ``damping = 0`` performance stands on its own; small positive
values shade short appearances down without erasing them.

The three multipliers that follow are context, not performance: how strong the
opponent was, how much the competition is worth and how deep into it the match
sat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "config"

# FotMob does not rate players below roughly ten minutes.
RATING_MINUTE_FLOOR = 10


@dataclass
class ScoringConfig:
    """Model parameters, loaded from config/ and overridable."""

    position_groups: dict[str, dict[str, float]]
    penalties: dict[str, float]
    rating: dict[str, float]
    competitions: dict[str, float]
    stages: dict[str, float]

    minutes_damping: float = 0.0
    """Exponent on ``minutes/90``. 0 leaves performance untouched."""

    reference_quantile: float = 0.95
    """Where a statistic is considered 'a full contribution'."""

    opponent_floor: float = 0.70
    opponent_range: float = 0.60
    """Opponent strength 0..1 maps onto ``floor .. floor + range``.

    A multiplier straight from the 0..1 strength would zero out matches against
    weak sides; this keeps every match worth something while still separating a
    Clasico from a cup tie against amateurs.
    """

    season_quality_weight: float = 0.50
    """How much of the season total is 'level' rather than 'matches played'.

    ``0`` is a raw sum (a 60-match calendar buries a 35-match star). ``1`` is
    mean × ``season_ref_matches``, as if everyone played the same body of work.
    """

    season_ref_matches: int = 40
    """Campaign length the quality term pretends everyone played."""

    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, config_dir: Path | None = None, **overrides: Any) -> ScoringConfig:
        config_dir = config_dir or CONFIG_DIR
        positions = yaml.safe_load(
            (config_dir / "positions.yml").read_text(encoding="utf-8")
        )
        competitions = yaml.safe_load(
            (config_dir / "competitions.yml").read_text(encoding="utf-8")
        )
        return cls(
            position_groups=positions["position_groups"],
            penalties=positions["penalties"],
            rating=positions["rating"],
            competitions={c["code"]: c["weight"] for c in competitions["competitions"]},
            stages=competitions["stages"],
            **overrides,
        )

    def stats_for(self, group: str) -> dict[str, float]:
        return self.position_groups.get(group, {})

    @property
    def all_stats(self) -> set[str]:
        used = {s for group in self.position_groups.values() for s in group}
        return used | set(self.penalties)


# --------------------------------------------------------------------- #
# Preparation
# --------------------------------------------------------------------- #


def add_derived(stats: pd.DataFrame) -> pd.DataFrame:
    """Goalkeeper metrics FotMob implies rather than states."""
    out = stats.copy()
    if {"saves", "goals_conceded"} <= set(out.columns):
        attempts = out.saves.fillna(0) + out.goals_conceded.fillna(0)
        out["save_pct"] = (out.saves / attempts).where(attempts > 0)
        out["clean_sheet"] = (out.goals_conceded == 0).astype(float)
        # Only goalkeepers concede; everyone else must stay out of the average.
        outfield = out.position_group != "GK"
        out.loc[outfield, ["save_pct", "clean_sheet"]] = pd.NA
    return out


def fill_structural_zeros(
    stats: pd.DataFrame, columns: list[str], covered_only: bool = True
) -> pd.DataFrame:
    """Turn 'the event never happened' NaNs into zeros.

    FotMob omits a statistic when its count is zero, so a player who never shot
    has no ``shots`` row at all. That is a genuine zero. It is only safe where
    the match itself was fully covered: in the three finals FotMob tracked
    without advanced stats, a missing xG means unmeasured, not nil.
    """
    out = stats.copy()
    present = [c for c in columns if c in out.columns]
    mask = out.coverage_level.eq("xG") if covered_only and "coverage_level" in out else True
    for column in present:
        out.loc[mask, column] = out.loc[mask, column].fillna(0.0)
    return out


def reference_levels(
    stats: pd.DataFrame, config: ScoringConfig, min_minutes: int = 60
) -> pd.DataFrame:
    """The 95th-percentile value of each statistic within each position group.

    Computed over full appearances only, so the yardstick is 'a good starter's
    match' and does not drift down as substitutes pile into the sample.
    """
    starters = stats[stats.minutes.fillna(0) >= min_minutes]
    rows = []
    for group, weights in config.position_groups.items():
        subset = starters[starters.position_group == group]
        for stat in weights:
            if stat not in subset.columns:
                continue
            value = subset[stat].quantile(config.reference_quantile)
            # Rare events flatten the percentile to zero -- 95% of defenders
            # score no goals in a match -- which would silently drop the
            # statistic and leave a scoring centre-back uncredited. One event
            # then counts as a full contribution, which is about right.
            if not value or pd.isna(value):
                value = max(subset[stat].quantile(0.99) or 0.0, 1.0)
            rows.append({"position_group": group, "stat": stat, "reference": value})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------- #


def base_performance(
    stats: pd.DataFrame, config: ScoringConfig, references: pd.DataFrame
) -> pd.DataFrame:
    """Weighted contribution plus rating, per player-match."""
    out = stats.copy()
    lookup = references.set_index(["position_group", "stat"])["reference"].to_dict()

    contribution = pd.Series(0.0, index=out.index)
    weight_total = pd.Series(0.0, index=out.index)

    for group, weights in config.position_groups.items():
        rows = out.position_group == group
        if not rows.any():
            continue
        for stat, weight in weights.items():
            if stat not in out.columns:
                continue
            reference = lookup.get((group, stat))
            if not reference or pd.isna(reference):
                continue
            scaled = (out.loc[rows, stat].astype(float) / reference).clip(upper=2.0)
            contribution.loc[rows] = contribution.loc[rows].add(
                scaled.fillna(0.0) * weight, fill_value=0.0
            )
            weight_total.loc[rows] += weight

    out["stats_score"] = (contribution / weight_total.replace(0, pd.NA)).fillna(0.0)

    penalty = pd.Series(0.0, index=out.index)
    for stat, weight in config.penalties.items():
        if stat in out.columns:
            penalty += pd.to_numeric(out[stat], errors="coerce").fillna(0.0) * weight
    out["penalty_score"] = penalty / max(len(config.penalties), 1)

    baseline = config.rating["baseline"]
    scale = config.rating["scale"]
    rating = pd.to_numeric(out.rating, errors="coerce")
    rating_component = ((rating - baseline) / scale).clip(-1.0, 1.0)
    # Cameos below FotMob's rating floor fall back on what they actually did.
    out["rating_score"] = rating_component
    weight = config.rating["weight"]
    blended = (1 - weight) * out.stats_score + weight * rating_component
    out["performance"] = (
        (blended.where(rating_component.notna(), out.stats_score) + out.penalty_score)
        .clip(lower=0.0)
        .astype(float)
    )
    return out


def apply_context(
    scored: pd.DataFrame, config: ScoringConfig
) -> pd.DataFrame:
    """Turn a performance into a Match Score using the match's context."""
    out = scored.copy()
    minutes_ratio = (out.minutes.fillna(0) / 90).clip(0, 1)
    out["reliability"] = (
        minutes_ratio**config.minutes_damping if config.minutes_damping else 1.0
    )
    out["competition_weight"] = out.competition_code.map(config.competitions).fillna(1.0)
    out["stage_weight"] = out.stage.map(config.stages).fillna(1.0)
    out["opponent_multiplier"] = (
        config.opponent_floor + config.opponent_range * out.opponent_strength.fillna(0.5)
    )
    out["match_score"] = (
        out.performance
        * out.reliability
        * out.opponent_multiplier
        * out.competition_weight
        * out.stage_weight
    ).astype(float)
    return out


def _club(teams: pd.Series) -> str | None:
    """The club a player belongs to, ignoring national-team call-ups."""
    modes = teams.mode()
    return modes.iloc[0] if len(modes) else None


def season_score(
    scored: pd.DataFrame,
    by: str = "opta_player_id",
    quality_weight: float | None = None,
    ref_matches: int | None = None,
    config: ScoringConfig | None = None,
) -> pd.DataFrame:
    """Aggregate Match Scores into a season total per player.

    The published total is a blend of volume (sum) and level (mean × a
    reference campaign). Playing 55 average games should not automatically
    beat 35 excellent ones.
    """
    if config is not None:
        quality_weight = config.season_quality_weight if quality_weight is None else quality_weight
        ref_matches = config.season_ref_matches if ref_matches is None else ref_matches
    quality_weight = 0.50 if quality_weight is None else quality_weight
    ref_matches = 40 if ref_matches is None else ref_matches

    club_rows = scored[~scored.competition_code.str.startswith("INT-", na=False)]
    clubs = club_rows.groupby(by)["team"].agg(_club).rename("club")

    grouped = scored.groupby(by, as_index=False).agg(
        player=("player", "last"),
        position_group=("position_group", "last"),
        matches=("match_score", "size"),
        minutes=("minutes", "sum"),
        match_score_sum=("match_score", "sum"),
        mean_match_score=("match_score", "mean"),
        median_match_score=("match_score", "median"),
        mean_performance=("performance", "mean"),
        mean_rating=("rating", "mean"),
        goals=("goals", "sum"),
        assists=("assists", "sum"),
        competitions=("competition_code", "nunique"),
    )
    grouped["season_score"] = (1 - quality_weight) * grouped.match_score_sum + quality_weight * (
        grouped.mean_match_score * ref_matches
    )
    grouped = grouped.merge(clubs, on=by, how="left")
    return grouped.sort_values("season_score", ascending=False).reset_index(drop=True)
