"""KYRE Streamlit Router V203 — Passing Yards universal tokens Step 2.

Additive over frozen V202. Only active NFL Passing Yards advances from V51 to
presentation-only V52. NFL Moneyline and every unrelated route remain delegated
through V202 unchanged.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v202 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V203 • PASSING YARDS UNIVERSAL TOKENS STEP 2"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v202"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v52"
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)

def _active_route() -> tuple[str, str]:
    return prior._active_route()

def render_app() -> None:
    sport, market = _active_route()
    if sport != "NFL" or market != PASSING_MARKET:
        return prior.render_app()

    original = prior.PASSING_HUB
    prior.PASSING_HUB = PASSING_HUB
    try:
        return prior.render_app()
    finally:
        prior.PASSING_HUB = original

__all__ = [
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PASSING_HUB",
    "PASSING_MARKET",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_route",
    "record_bootstrap_import_ms",
    "render_app",
]
