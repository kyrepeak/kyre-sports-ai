"""KYRE Streamlit Router V137 — NFL Passing Yards compact dashboard route.

V137 owns only exact NFL -> Passing Yards and advances that route from certified
V35 to display-only V36. Every other route delegates to frozen V136 unchanged.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v128 as passing_route
import streamlit_memory_lazy_router_v136 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V137 • NFL PASSING YARDS COMPACT DASHBOARD"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v136"
ACTIVE_PASSING_YARDS_HUB = "nfl_passing_yards_hub_v36"
PASSING_YARDS_MARKET = passing_route.PASSING_YARDS_MARKET
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _render_direct_passing() -> None:
    original_hub = passing_route.ACTIVE_PASSING_YARDS_HUB
    passing_route.ACTIVE_PASSING_YARDS_HUB = ACTIVE_PASSING_YARDS_HUB
    try:
        return passing_route._render_direct_passing()
    finally:
        passing_route.ACTIVE_PASSING_YARDS_HUB = original_hub


def render_app() -> None:
    if passing_route._passing_route_active():
        return _render_direct_passing()
    return prior.render_app()


__all__ = [
    "ACTIVE_PASSING_YARDS_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "PASSING_YARDS_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_render_direct_passing",
    "record_bootstrap_import_ms",
    "render_app",
]
