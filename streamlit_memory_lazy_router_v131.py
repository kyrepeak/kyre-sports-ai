"""KYRE Streamlit Router V131 — NFL Moneyline V12 speed transport.

V131 is additive over frozen Router V130. It advances only exact
NFL -> Moneyline to V12. Passing Yards and every other route remain delegated
through the frozen router chain unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v130 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V131 • NFL MONEYLINE V12 SPEED CACHE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v130"
NFL_SPORT_LABEL = "NFL"
MONEYLINE_MARKET = "Moneyline"
ACTIVE_MONEYLINE_HUB = "nfl_moneyline_hub_v12"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _moneyline_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == NFL_SPORT_LABEL
        and str(st.session_state.get("ks_nfl_market_touch") or "") == MONEYLINE_MARKET
    )


def _render_nfl_v131(market: str) -> None:
    market = str(market or "Slate")
    if market != MONEYLINE_MARKET:
        raise RuntimeError("Router V131 direct handler is Moneyline only.")
    module = root._import(ACTIVE_MONEYLINE_HUB)
    return module.render_nfl_hub(market)


def _render_direct_moneyline() -> None:
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES
    root._render_nfl = _render_nfl_v131
    if "nfl_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("nfl_",)
    try:
        return root.render_app()
    finally:
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    if _moneyline_route_active():
        return _render_direct_moneyline()
    return prior.render_app()


__all__ = [
    "ACTIVE_MONEYLINE_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "MONEYLINE_MARKET",
    "NFL_SPORT_LABEL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_moneyline_route_active",
    "_render_direct_moneyline",
    "_render_nfl_v131",
    "record_bootstrap_import_ms",
    "render_app",
]
