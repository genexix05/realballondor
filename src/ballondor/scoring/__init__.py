"""Scoring stubs (applied in a later milestone)."""

from __future__ import annotations


def match_score_stub(
    base_performance: float,
    opponent_multiplier: float = 1.0,
    competition_multiplier: float = 1.0,
    stage_multiplier: float = 1.0,
) -> float:
    return (
        base_performance
        * opponent_multiplier
        * competition_multiplier
        * stage_multiplier
    )
