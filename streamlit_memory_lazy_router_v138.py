"""KYRE Streamlit Router V138 — Passing Yards smart-slate route.

Additive over frozen Router V137. Advances only exact NFL -> Passing Yards to
V37 and filters obsolete empty-slate informational notices on that route. Every
other route delegates to V137 unchanged.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v137 as prior
from nfl_passing_yards_slate_controller_v1 import is_empty_slate_notice

MODEL_VERSION = "KYRE STREAMLIT ROUTER V138 • NFL PASSING YARDS SMART SLATE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v137"
NFL_SPORT_LABEL = "NFL"
PASSING_YARDS_MARKET = "Passing Yards"
ACTIVE_PASSING_YARDS_HUB = "nfl_passing_yards_hub_v37"
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


def _render_nfl_v138(market: str) -> None:
    market = str(market or "Slate")
    if market != PASSING_YARDS_MARKET:
        raise RuntimeError("Router V138 direct handler is Passing Yards only.")
    module = root._import(ACTIVE_PASSING_YARDS_HUB)
    return module.render_nfl_hub(market)


def _render_direct_passing() -> None:
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES
    original_info = st.info

    def filtered_info(body: Any, *args: Any, **kwargs: Any):
        if is_empty_slate_notice(body):
            return None
        return original_info(body, *args, **kwargs)

    root._render_nfl = _render_nfl_v138
    st.info = filtered_info
    if "nfl_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("nfl_",)
    try:
        return root.render_app()
    finally:
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes
        st.info = original_info


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
    "_render_nfl_v138",
    "record_bootstrap_import_ms",
    "render_app",
]
