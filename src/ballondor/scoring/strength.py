"""Opponent strength on a single 0..1 scale, as of kickoff.

The UEFA club coefficient is the natural measure of how good a club is, but it
only separates clubs that play in Europe. In the 2025/26 dataset just 113 of
489 clubs do, so in 87% of domestic matches the coefficient cannot tell the
opponents apart -- a Betis-Levante would carry the same weight as a Betis-Oviedo.

Strength is therefore built from two components and blended:

``uefa``
    The five-year club coefficient in force during the season. Rewards
    sustained European pedigree, and is zero for most clubs.
``domestic``
    Points per game in the club's own league, scaled by that league's UEFA
    country coefficient so a mid-table Premier League side is not treated as
    the equal of a mid-table Eredivisie side. Covers every club.

Both are read as of kickoff. The domestic component blends last season's final
table with this season's form so far, shrinking towards the former early on
when a handful of matches say very little. Only matches played strictly before
kickoff count, so a team's rating on matchday 20 never reflects matchday 21.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

import pandas as pd

# Kassiesa country codes for the leagues we scale.
LEAGUE_COUNTRY = {
    "ESP-La Liga": "Esp",
    "ENG-Premier League": "Eng",
    "GER-Bundesliga": "Ger",
    "ITA-Serie A": "Ita",
    "FRA-Ligue 1": "Fra",
}

# FotMob and kassiesa disagree on a handful of club names in ways that
# normalisation cannot bridge.
# Deliberately not a catch-all: bare "paris" is left alone because Paris FC and
# Paris Saint-Germain both play in Ligue 1, and collapsing them would hand a
# promoted side the champions' coefficient.
CLUB_ALIASES = {
    "athletic club": "athletic bilbao",
    "brest": "stade brestois",
    "rennes": "stade rennais",
    "lyon": "olympique lyon",
    "marseille": "olympique marseille",
    "inter": "internazionale",
    "internazionale milano": "internazionale",
    "psg": "paris saint germain",
    "brighton": "brighton hove albion",
    "manchester utd": "manchester united",
    "newcastle": "newcastle united",
    "spurs": "tottenham hotspur",
    "tottenham": "tottenham hotspur",
    "wolves": "wolverhampton wanderers",
    "monchengladbach": "borussia monchengladbach",
    "bayern munich": "bayern munchen",
}

# Nation names differ between FotMob and the ranking source beyond what
# accent-stripping fixes.
NATION_ALIASES = {
    "bosnia and herzegovina": "bosnia",
    "republic of ireland": "ireland",
    "ivory coast": "ivory coast",
    "cape verde islands": "cape verde",
    "korea republic": "south korea",
    "korea dpr": "north korea",
    "united states": "usa",
    "china pr": "china",
    "czechia": "czech republic",
    "turkiye": "turkey",
}

# Prefixes and suffixes clubs carry inconsistently across sources.
_NOISE = {
    "fc", "cf", "ac", "as", "sc", "ss", "ssc", "afc", "cd", "ud", "rc", "rcd",
    "sv", "vfl", "vfb", "tsg", "bsc", "us", "ogc", "spal", "aj", "sd", "osc",
    "losc", "calcio", "cp",
}


@dataclass
class StrengthConfig:
    """Model parameters. All tunable; none are data."""

    prior_matches: float = 8.0
    """How many matches of last season's form this season's record must beat.

    At ``n`` matches played the blend is ``n / (n + prior_matches)`` current
    form, so matchday 8 weighs the two halves equally.
    """

    league_exponent: float = 0.5
    """How hard the country coefficient separates leagues.

    ``0`` treats every league as equal, ``1`` scales strength linearly with the
    country coefficient. ``0.5`` keeps Ligue 1 clearly below the Premier League
    without halving them.
    """

    uefa_weight: float = 0.35
    """Share of the final score coming from European pedigree."""

    max_points_per_game: float = 3.0
    aliases: dict[str, str] = field(default_factory=lambda: dict(CLUB_ALIASES))


# --------------------------------------------------------------------- #
# Name normalisation
# --------------------------------------------------------------------- #


def normalise_club(name: str) -> str:
    """A join key that survives accents, punctuation and FC/CF-style noise.

    Founding years are dropped too, so kassiesa's "1899 Hoffenheim" and
    "1.FC Heidenheim" line up with FotMob's plainer spellings.
    """
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    text = "".join(c.lower() if c.isalnum() else " " for c in text)
    words = [w for w in text.split() if w]
    trimmed = [w for w in words if w not in _NOISE and not w.isdigit()]
    return " ".join(trimmed or words)


def _apply_aliases(key: str, aliases: dict[str, str]) -> str:
    return normalise_club(aliases.get(key, key))


def normalise_nation(name: str) -> str:
    """Join key for national teams: accents and punctuation only.

    Unlike clubs, nation names carry no FC/CF-style noise to strip, and doing so
    would mangle names like "US Virgin Islands".
    """
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    key = " ".join("".join(c.lower() if c.isalnum() else " " for c in text).split())
    return NATION_ALIASES.get(key, key)


# --------------------------------------------------------------------- #
# Domestic form
# --------------------------------------------------------------------- #


def _as_timestamp(values: pd.Series) -> pd.Series:
    """Naive nanosecond timestamps, so as-of merges never trip over units."""
    out = pd.to_datetime(values, utc=True).dt.tz_localize(None)
    return out.astype("datetime64[ns]")


def to_long(results: pd.DataFrame) -> pd.DataFrame:
    """One row per team per match, with points earned."""
    base = ["match_id", "competition_code", "kickoff"]
    home = results[[*base, "home_team_id", "home_team", "home_goals", "away_goals"]].rename(
        columns={"home_team_id": "team_id", "home_team": "team",
                 "home_goals": "goals_for", "away_goals": "goals_against"}
    )
    away = results[[*base, "away_team_id", "away_team", "away_goals", "home_goals"]].rename(
        columns={"away_team_id": "team_id", "away_team": "team",
                 "away_goals": "goals_for", "home_goals": "goals_against"}
    )
    long = pd.concat([home, away], ignore_index=True)
    long["points"] = (
        (long.goals_for > long.goals_against) * 3 + (long.goals_for == long.goals_against) * 1
    )
    long["kickoff"] = _as_timestamp(long["kickoff"])
    return long.sort_values("kickoff").reset_index(drop=True)


def final_table(long: pd.DataFrame) -> pd.DataFrame:
    """End-of-season points per game per team, per competition."""
    table = (
        long.groupby(["competition_code", "team_id", "team"], as_index=False)
        .agg(played=("points", "size"), points=("points", "sum"),
             goals_for=("goals_for", "sum"), goals_against=("goals_against", "sum"))
    )
    table["ppg"] = table.points / table.played
    return table


def baseline_ppg(previous: pd.DataFrame) -> pd.DataFrame:
    """Last season's points per game, the prior for this season's form.

    Promoted clubs have no top-flight record, so they inherit the weakest
    baseline in the league they are joining -- which is what the previous
    season's evidence actually supports.
    """
    table = final_table(to_long(previous))
    return table[["competition_code", "team_id", "team", "ppg"]].rename(
        columns={"ppg": "baseline_ppg"}
    )


def form_timeline(current: pd.DataFrame) -> pd.DataFrame:
    """Running league record for each team after every match they played."""
    long = to_long(current)
    long = long.sort_values(["team_id", "kickoff"])
    long["cum_points"] = long.groupby("team_id")["points"].cumsum()
    long["cum_played"] = long.groupby("team_id").cumcount() + 1
    return long[["team_id", "team", "competition_code", "kickoff", "cum_points", "cum_played"]]


def domestic_strength(
    current: pd.DataFrame,
    previous: pd.DataFrame,
    queries: pd.DataFrame,
    country_coefficients: pd.DataFrame,
    config: StrengthConfig | None = None,
) -> pd.DataFrame:
    """Domestic strength for each ``(team_id, kickoff)`` pair in ``queries``.

    ``queries`` needs ``team_id`` and ``kickoff``; the result adds the blended
    points per game and the league-scaled 0..1 score. Only league matches that
    finished before ``kickoff`` contribute, so nothing leaks backwards.
    """
    config = config or StrengthConfig()

    baseline = baseline_ppg(previous)
    worst = baseline.groupby("competition_code")["baseline_ppg"].min().rename("worst_ppg")
    home_league = (
        current.pipe(to_long)[["team_id", "competition_code"]].drop_duplicates("team_id")
    )
    baseline = home_league.merge(
        baseline[["team_id", "baseline_ppg"]], on="team_id", how="left"
    ).merge(worst, on="competition_code", how="left")
    baseline["baseline_ppg"] = baseline.baseline_ppg.fillna(baseline.worst_ppg)

    timeline = form_timeline(current)
    queries = queries.copy()
    queries["kickoff"] = _as_timestamp(queries["kickoff"])

    # allow_exact_matches=False keeps a match from informing its own rating.
    resolved = pd.merge_asof(
        queries.sort_values("kickoff"),
        timeline.sort_values("kickoff")[["team_id", "kickoff", "cum_points", "cum_played"]],
        on="kickoff",
        by="team_id",
        direction="backward",
        allow_exact_matches=False,
    )
    resolved[["cum_points", "cum_played"]] = resolved[["cum_points", "cum_played"]].fillna(0)

    # Renamed because a query row already carries the competition of the match
    # being rated, which is not necessarily the team's own league.
    resolved = resolved.merge(
        baseline[["team_id", "competition_code", "baseline_ppg"]].rename(
            columns={"competition_code": "home_league"}
        ),
        on="team_id",
        how="left",
    )
    prior = config.prior_matches
    resolved["blended_ppg"] = (
        resolved.baseline_ppg * prior + resolved.cum_points
    ) / (prior + resolved.cum_played)

    country = country_coefficients.drop_duplicates("country").set_index("country")[
        "country_coefficient"
    ]
    scale = country / country.max()
    resolved["league_factor"] = (
        resolved.home_league.map(LEAGUE_COUNTRY).map(scale) ** config.league_exponent
    )
    resolved["domestic_score"] = (
        (resolved.blended_ppg / config.max_points_per_game) * resolved.league_factor
    )
    return resolved


# --------------------------------------------------------------------- #
# Blend with the UEFA club coefficient
# --------------------------------------------------------------------- #


def attach_uefa(
    teams: pd.DataFrame, coefficients: pd.DataFrame, config: StrengthConfig | None = None
) -> pd.DataFrame:
    """Match FotMob team names to UEFA club coefficients.

    Unmatched clubs keep a coefficient of zero, which is also the honest value
    for a club that has not played in Europe in five years.
    """
    config = config or StrengthConfig()
    left = teams.copy()
    left["join_key"] = left["team"].map(lambda n: _apply_aliases(normalise_club(n), config.aliases))

    right = coefficients.copy()
    right["join_key"] = right["club"].map(
        lambda n: _apply_aliases(normalise_club(n), config.aliases)
    )
    # Distinct clubs can share a key across countries ("Rangers"). Keeping the
    # stronger one is the safer guess, and ambiguous_club_keys() surfaces them.
    right = right.sort_values("coefficient", ascending=False).drop_duplicates("join_key")

    merged = left.merge(
        right[["join_key", "coefficient", "rank"]].rename(
            columns={"coefficient": "uefa_coefficient", "rank": "uefa_rank"}
        ),
        on="join_key",
        how="left",
    )
    merged["uefa_matched"] = merged.uefa_coefficient.notna()
    merged["uefa_coefficient"] = merged.uefa_coefficient.fillna(0.0)
    return merged


def ambiguous_club_keys(
    coefficients: pd.DataFrame, config: StrengthConfig | None = None
) -> pd.DataFrame:
    """Coefficient rows whose normalised name collides with another club."""
    config = config or StrengthConfig()
    frame = coefficients.copy()
    frame["join_key"] = frame["club"].map(
        lambda n: _apply_aliases(normalise_club(n), config.aliases)
    )
    counts = frame.join_key.value_counts()
    return frame[frame.join_key.isin(counts[counts > 1].index)].sort_values("join_key")


def blend(strengths: pd.DataFrame, config: StrengthConfig | None = None) -> pd.DataFrame:
    """Combine the European and domestic components into ``opponent_strength``.

    The UEFA coefficient is square-rooted before scaling: its raw distribution
    is dominated by a handful of clubs (Real Madrid 143.5 against a median
    under 5), so a linear scale would collapse everyone else to zero.
    """
    config = config or StrengthConfig()
    out = strengths.copy()
    root = out.uefa_coefficient.clip(lower=0) ** 0.5
    out["uefa_score"] = root / root.max() if root.max() else 0.0
    out["opponent_strength"] = (
        config.uefa_weight * out.uefa_score
        + (1 - config.uefa_weight) * out.domestic_score.fillna(0.0)
    ).clip(0, 1)
    return out
