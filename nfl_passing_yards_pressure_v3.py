"""NFL Passing Yards pressure V3 — UTC-safe recent-game bridge.

Additive wrapper over certified V2. Step 4 reuses the V1 recent-game helper,
which historically compared a timezone-aware ESPN event timestamp with a naive
calendar cutoff. On live opening-week slates that can raise ``TypeError`` before
any pressure card renders.

V3 leaves the certified pressure math unchanged. It temporarily gives the V1
pressure module a lightweight defense-module proxy whose only override is the
UTC-safe completed-event selector already certified by pass-defense V3. All
other defense reads are forwarded to the real V1 module and the original module
reference is restored in a ``finally`` block.

No projection math, probability, sportsbook influence, identity, CFB behavior,
or fail-closed contract changes. Sportsbook projection influence remains 0.0%.
"""
from __future__ import annotations

from typing import Any

import nfl_passing_yards_defense_v3 as defense_v3
import nfl_passing_yards_pressure_v1 as base
import nfl_passing_yards_pressure_v2 as prior

MODEL_VERSION = "NFL PASSING YARDS PRESSURE V3 • UTC-SAFE RECENT GAME BRIDGE"
FROZEN_PRIOR = "nfl_passing_yards_pressure_v2"


class _UtcDefenseProxy:
    """Forward every V1 defense read except completed-event date selection."""

    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> Any:
        if name == "_completed_event_rows":
            return defense_v3._completed_event_rows_utc
        return getattr(self._wrapped, name)


def _with_utc_defense(func, *args, **kwargs):
    original_defense = base.defense
    base.defense = _UtcDefenseProxy(original_defense)
    try:
        return func(*args, **kwargs)
    finally:
        base.defense = original_defense


def build_pressure_matchup(
    offense_team_id: str,
    offense_team_name: str,
    defense_team_id: str,
    defense_team_name: str,
    year: int,
    season_type: int,
    cutoff_date: str,
) -> dict:
    row = dict(
        _with_utc_defense(
            prior.build_pressure_matchup,
            offense_team_id,
            offense_team_name,
            defense_team_id,
            defense_team_name,
            year,
            season_type,
            cutoff_date,
        )
        or {}
    )
    row["timezone_normalization"] = "UTC"
    row["projection_adjustment"] = 0.0
    row["sportsbook_influence"] = 0.0
    return row


parse_defensive_pressure = prior.parse_defensive_pressure
parse_offense_protection = prior.parse_offense_protection
parse_recent_sacks_made = prior.parse_recent_sacks_made
parse_recent_sacks_taken = prior.parse_recent_sacks_taken
pressure_label = prior.pressure_label

__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "build_pressure_matchup",
    "parse_defensive_pressure",
    "parse_offense_protection",
    "parse_recent_sacks_made",
    "parse_recent_sacks_taken",
    "pressure_label",
]
