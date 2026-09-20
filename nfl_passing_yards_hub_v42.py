"""NFL Passing Yards V42 — Step 7 render-time player identity gate.

Additive over frozen V41. The only new behavior is a final exact-event/current-
roster check before QB identity reaches the existing player cards.
"""
from __future__ import annotations

import nfl_passing_yards_hub_v41 as prior
import nfl_passing_yards_identity_v1 as identity
from nfl_prop_app_eligibility_v1 import guard_passing_identity

MODEL_VERSION = "NFL PASSING YARDS V42 • STEP 7 APP IDENTITY FAIL-CLOSED"
FROZEN_PRIOR = "nfl_passing_yards_hub_v41"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_RESOLVE = identity.resolve_matchup_identity


def _resolve_matchup_identity_step7(game: dict, season_year: int) -> dict:
    resolved = _ORIGINAL_RESOLVE(game, season_year)
    return guard_passing_identity(game, resolved)


def render_nfl_passing_yards_hub() -> None:
    original = identity.resolve_matchup_identity
    identity.resolve_matchup_identity = _resolve_matchup_identity_step7
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        identity.resolve_matchup_identity = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V42 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_resolve_matchup_identity_step7",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
