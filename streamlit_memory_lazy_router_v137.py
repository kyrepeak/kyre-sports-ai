"""KYRE Streamlit Router V137 — NFL Passing Yards compact dashboard route.

V137 is additive over frozen Router V136. It advances only exact
NFL -> Passing Yards to V36 compact-dashboard presentation. NFL Spread remains
owned by V136 and every other route remains delegated through the frozen chain.

Passing Yards projection/probability/market math and sportsbook influence stay
frozen; this router changes route presentation ownership only.
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


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _passing_yards_route_active() -> bool:
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


def _render_direct_passing_yards() -> None:
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
    """Own exact NFL -> Passing Yards; delegate every other route to V136."""
    if _passing_yards_route_active():
        return _render_direct_passing_yards()
    return prior.render_app()


__all__ = [
    "ACTIVE_PASSING_YARDS_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "NFL_SPORT_LABEL",
    "PASSING_YARDS_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_passing_yards_route_active",
    "_render_direct_passing_yards",
    "_render_nfl_v137",
    "record_bootstrap_import_ms",
    "render_app",
]
