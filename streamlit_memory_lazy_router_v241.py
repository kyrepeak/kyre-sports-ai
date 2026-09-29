"""Streamlit Router V241 — CFB Top Picks Step 1 route ownership.

Additive over frozen V240. It adds one College Football market, Top Picks, and
owns only that exact route. Existing CFB Moneyline, Over/Under, Game Total,
NFL, MLB, and WNBA routes continue through the frozen router chain unchanged.
"""
from __future__ import annotations

import importlib

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v77 as cfb_route_base
import streamlit_memory_lazy_router_v240 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V241 • CFB TOP PICKS STEP 1"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v240"
CFB_SPORT_LABEL = "College Football"
TOP_PICKS_MARKET = "Top Picks"
TOP_PICKS_PAGE = "cfb_top_picks_page_v1"
SPORT_KEY = "ks_sport_touch"
CFB_MARKET_KEY = "ks_cfb_market_touch"
ROUTE_QUERY_SPORT = cfb_route_base.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = cfb_route_base.ROUTE_QUERY_MARKET
ROUTE_OWNERSHIP_ONLY = True
MAY_MODIFY_EXISTING_CFB_PRODUCTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _query_value(key: str) -> str:
    try:
        raw = st.query_params.get(key)
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _top_picks_market_options() -> tuple[str, ...]:
    options = list(cfb_route_base.CFB_MARKETS)
    if TOP_PICKS_MARKET not in options:
        options.append(TOP_PICKS_MARKET)
    return tuple(options)


def _install_top_picks_market_option() -> None:
    cfb_route_base.CFB_MARKETS = _top_picks_market_options()


def _cold_top_picks_query_requested() -> bool:
    return (
        _query_value(ROUTE_QUERY_SPORT) == CFB_SPORT_LABEL
        and _query_value(ROUTE_QUERY_MARKET) == TOP_PICKS_MARKET
    )


def _active_top_picks_route() -> bool:
    return (
        str(st.session_state.get(SPORT_KEY) or "").strip() == CFB_SPORT_LABEL
        and str(st.session_state.get(CFB_MARKET_KEY) or "").strip() == TOP_PICKS_MARKET
    )


def _prime_top_picks_state_from_query() -> None:
    st.session_state[SPORT_KEY] = CFB_SPORT_LABEL
    st.session_state[CFB_MARKET_KEY] = TOP_PICKS_MARKET


def _persist_top_picks_query() -> None:
    try:
        if _query_value(ROUTE_QUERY_SPORT) != CFB_SPORT_LABEL:
            st.query_params[ROUTE_QUERY_SPORT] = CFB_SPORT_LABEL
        if _query_value(ROUTE_QUERY_MARKET) != TOP_PICKS_MARKET:
            st.query_params[ROUTE_QUERY_MARKET] = TOP_PICKS_MARKET
    except Exception:
        pass


def _render_cfb_top_picks_v241(market: str) -> None:
    sport = str(st.session_state.get(SPORT_KEY) or "").strip()
    normalized = str(market or "").strip()
    if sport != CFB_SPORT_LABEL or normalized != TOP_PICKS_MARKET:
        raise RuntimeError("Router V241 direct handler owns only College Football -> Top Picks.")

    _persist_top_picks_query()
    module = importlib.import_module(TOP_PICKS_PAGE)
    return module.render_cfb_hub(
        normalized,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def _render_direct_top_picks() -> None:
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    _install_top_picks_market_option()
    root.st.selectbox = cfb_route_base._selectbox_v77
    root._render_nfl = _render_cfb_top_picks_v241
    if "cfb_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("cfb_",)

    try:
        return root.render_app()
    finally:
        root.st.selectbox = original_selectbox
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def _delegate_with_top_picks_option() -> None:
    _install_top_picks_market_option()
    return prior.render_app()


def render_app() -> None:
    _install_top_picks_market_option()
    if not _active_top_picks_route() and _cold_top_picks_query_requested():
        _prime_top_picks_state_from_query()

    if _active_top_picks_route():
        return _render_direct_top_picks()

    return _delegate_with_top_picks_option()


__all__ = [
    "CFB_MARKET_KEY",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MAY_MODIFY_EXISTING_CFB_PRODUCTS",
    "MODEL_VERSION",
    "ROUTE_OWNERSHIP_ONLY",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_KEY",
    "TOP_PICKS_MARKET",
    "TOP_PICKS_PAGE",
    "_active_top_picks_route",
    "_cold_top_picks_query_requested",
    "_delegate_with_top_picks_option",
    "_install_top_picks_market_option",
    "_persist_top_picks_query",
    "_prime_top_picks_state_from_query",
    "_query_value",
    "_render_cfb_top_picks_v241",
    "_render_direct_top_picks",
    "_top_picks_market_options",
    "record_bootstrap_import_ms",
    "render_app",
]
