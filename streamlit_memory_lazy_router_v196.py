"""KYRE Streamlit Router V196 — Passing Yards visual upgrade Step 5.

Additive over frozen V195. Only active NFL Passing Yards advances from V49 to
presentation-only V50. Every unrelated route delegates to V195.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v195 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V196 • PASSING YARDS FINAL RESPONSIVE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v195"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v50"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
PRESENTATION_ONLY = True

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
