"""NFL Passing Yards V45 — universal responsive polish.

Step 5 presentation-only wrapper over frozen V44. Adds the universal responsive
overlay at the final composition seam. No data/model/projection behavior changes.
"""
from __future__ import annotations

import nfl_passing_yards_hub_v44 as prior
from kyre_universal_responsive_v1 import build_responsive_css

MODEL_VERSION = "NFL PASSING YARDS V45 • UNIVERSAL RESPONSIVE POLISH"
FROZEN_PRIOR = "nfl_passing_yards_hub_v44"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

def _responsive_player_cards_html(captured: dict[str, list[str]]) -> str:
    return build_responsive_css() + prior._universal_player_cards_html(captured)

def render_nfl_passing_yards_hub() -> None:
    original_builder = prior._universal_player_cards_html
    prior._universal_player_cards_html = _responsive_player_cards_html
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._universal_player_cards_html = original_builder

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V45 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_responsive_player_cards_html",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
