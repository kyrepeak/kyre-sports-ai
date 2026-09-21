"""KYRE Streamlit Router V192 — Passing Yards visual upgrade Step 1.

Additive over frozen V191. Only active NFL Passing Yards advances from V45 to
presentation-only V46. Every unrelated market/sport delegates to V191.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v188 as passing_router
import streamlit_memory_lazy_router_v191 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V192 • PASSING YARDS TOP POLISH"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v191"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v46"
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

    original = passing_router.PASSING_HUB
    passing_router.PASSING_HUB = PASSING_HUB
    try:
        return prior.render_app()
    finally:
        passing_router.PASSING_HUB = original

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
