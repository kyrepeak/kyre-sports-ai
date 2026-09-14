"""KYRE Streamlit Router V127 — NFL Passing Yards combined player cards.

V127 is additive over frozen Router V126. It advances only exact
NFL -> Passing Yards to V34 combined player-first cards. Receiving Yards,
Rushing Yards, and every other route remain delegated to V126 unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v126 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V127 • NFL PASSING YARDS COMBINED PLAYER CARDS"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v126"
NFL_SPORT_LABEL = "NFL"
PASSING_YARDS_MARKET = "Passing Yards"
ACTIVE_PASSING_YARDS_HUB = "nfl_passing_yards_hub_v34"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _passing_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == NFL_SPORT_LABEL
        and str(st.session_state.get("ks_nfl_market_touch") or "") == PASSING_YARDS_MARKET
    )


def _render_nfl_v127(market: str) -> None:
    market = str(market or "Slate")
    if market != PASSING_YARDS_MARKET:
        raise RuntimeError("Router V127 direct handler is Passing Yards only.")
    module = root._import(ACTIVE_PASSING_YARDS_HUB)
    return module.render_nfl_hub(market)


def _render_direct_passing() -> None:
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES
    root._render_nfl = _render_nfl_v127
    if "nfl_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("nfl_",)
    try:
        return root.render_app()
    finally:
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    if _passing_route_active():
        return _render_direct_passing()
    return prior.render_app()


__all__ = [
    "ACTIVE_PASSING_YARDS_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "NFL_SPORT_LABEL",
    "PASSING_YARDS_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_passing_route_active",
    "_render_direct_passing",
    "_render_nfl_v127",
    "record_bootstrap_import_ms",
    "render_app",
]
