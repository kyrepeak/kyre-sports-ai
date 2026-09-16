"""KYRE Streamlit Router V137 — NFL Passing Yards compact dashboard route.

V137 is additive over frozen Router V136. It advances only exact
NFL -> Passing Yards to display-only V36 while every other route delegates to
V136 unchanged. Passing Yards V35 transport and V34/V33/V28 certified behavior
remain frozen underneath V36.

Sportsbook projection influence stays exactly 0.0% and stake sizing stays OFF.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v136 as prior


MODEL_VERSION = "KYRE STREAMLIT ROUTER V137 • NFL PASSING YARDS COMPACT DASHBOARD"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v136"
NFL_SPORT_LABEL = "NFL"
PASSING_YARDS_MARKET = "Passing Yards"
ACTIVE_PASSING_YARDS_HUB = "nfl_passing_yards_hub_v36"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _passing_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == NFL_SPORT_LABEL
        and str(st.session_state.get("ks_nfl_market_touch") or "") == PASSING_YARDS_MARKET
    )


def _render_nfl_v137(market: str) -> None:
    market = str(market or "Slate")
    if market != PASSING_YARDS_MARKET:
        raise RuntimeError("Router V137 direct handler is Passing Yards only.")
    module = root._import(ACTIVE_PASSING_YARDS_HUB)
    return module.render_nfl_hub(market)


def _render_direct_passing() -> None:
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES
    root._render_nfl = _render_nfl_v137
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
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_passing_route_active",
    "_render_direct_passing",
    "_render_nfl_v137",
    "record_bootstrap_import_ms",
    "render_app",
]
