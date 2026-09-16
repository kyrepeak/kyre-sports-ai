"""KYRE Streamlit Router V147 — Receiving Yards future multi-card render guard.

Additive over frozen Router V146. Advances only exact NFL -> Receiving Yards to
V16 while preserving Passing Yards V141 and every other certified route.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v146 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V147 • NFL RECEIVING YARDS FUTURE CARD RENDER FIX"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v146"
NFL_SPORT_LABEL = "NFL"
RECEIVING_YARDS_MARKET = "Receiving Yards"
ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v16"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _receiving_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == NFL_SPORT_LABEL
        and str(st.session_state.get("ks_nfl_market_touch") or "") == RECEIVING_YARDS_MARKET
    )


def _render_nfl_v147(market: str) -> None:
    market = str(market or "Slate")
    if market == "Receiving Yards":
        module = root._import(ACTIVE_RECEIVING_YARDS_HUB)
        return module.render_nfl_hub(market)
    raise RuntimeError("Router V147 direct handler is Receiving Yards only.")


def _render_direct_receiving() -> None:
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES
    root._render_nfl = _render_nfl_v147
    if "nfl_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("nfl_",)
    try:
        return root.render_app()
    finally:
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    if _receiving_route_active():
        return _render_direct_receiving()
    return prior.render_app()


__all__ = [
    "ACTIVE_RECEIVING_YARDS_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "NFL_SPORT_LABEL",
    "RECEIVING_YARDS_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_receiving_route_active",
    "_render_direct_receiving",
    "_render_nfl_v147",
    "record_bootstrap_import_ms",
    "render_app",
]
