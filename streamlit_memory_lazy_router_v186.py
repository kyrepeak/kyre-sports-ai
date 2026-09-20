"""KYRE Streamlit Router V186 — Passing Yards rolling next-game-date route.

Additive over frozen Router V185. V185 retains ownership of the certified
all-NFL same-run dropdown handoff. V186 consumes that exact handoff first, then
intercepts only the active NFL -> Passing Yards route before older direct-route
owners can restore V40. Every other route delegates to V185 unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v185 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V186 • NFL PASSING YARDS NEXT GAME DATE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v185"
PASSING_YARDS_MARKET = "Passing Yards"
NFL_SPORT_LABEL = "NFL"
ACTIVE_PASSING_YARDS_HUB = "nfl_passing_yards_hub_v41"

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _passing_route_active() -> bool:
    return (
        str(st.session_state.get(prior.SPORT_KEY) or "") == NFL_SPORT_LABEL
        and str(st.session_state.get(prior.NFL_MARKET_KEY) or "") == PASSING_YARDS_MARKET
    )


def _render_nfl_v186(market: str) -> None:
    normalized = str(market or "Slate")
    if normalized != PASSING_YARDS_MARKET:
        raise RuntimeError("Router V186 direct handler is Passing Yards only.")
    module = root._import(ACTIVE_PASSING_YARDS_HUB)
    return module.render_nfl_hub(normalized)


def _render_direct_passing() -> None:
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    root._render_nfl = _render_nfl_v186
    if "nfl_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("nfl_",)

    try:
        return root.render_app()
    finally:
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    # Keep V185 as the one certified owner of NFL dropdown state handoff.
    prior._consume_any_nfl_category_without_rerun()

    # Intercept Passing Yards here, before the frozen V141 direct route can
    # rebind root._render_nfl back to V40.
    if _passing_route_active():
        return _render_direct_passing()

    return prior.render_app()


__all__ = [
    "ACTIVE_PASSING_YARDS_HUB",
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NFL_SPORT_LABEL",
    "PASSING_YARDS_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_passing_route_active",
    "_render_direct_passing",
    "_render_nfl_v186",
    "record_bootstrap_import_ms",
    "render_app",
]
