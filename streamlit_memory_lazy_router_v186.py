"""KYRE Streamlit Router V186 — Passing Yards rolling next-game-date route.

Additive over frozen Router V185. V185 retains ownership of the certified
all-NFL same-run dropdown handoff. V186 only swaps the exact Passing Yards
renderer to V41, which prevents empty calendar dates from remaining on screen.

Every non-Passing-Yards route delegates unchanged.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v185 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V186 • NFL PASSING YARDS NEXT GAME DATE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v185"
PASSING_YARDS_MARKET = "Passing Yards"
ACTIVE_PASSING_YARDS_HUB = "nfl_passing_yards_hub_v41"

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> None:
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    def render_nfl_v186(market: str) -> None:
        normalized = str(market or "Slate")
        if normalized == PASSING_YARDS_MARKET:
            module = root._import(ACTIVE_PASSING_YARDS_HUB)
            return module.render_nfl_hub(normalized)
        return original_render_nfl(normalized)

    root._render_nfl = render_nfl_v186
    if "nfl_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("nfl_",)

    try:
        return prior.render_app()
    finally:
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


__all__ = [
    "ACTIVE_PASSING_YARDS_HUB",
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PASSING_YARDS_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
