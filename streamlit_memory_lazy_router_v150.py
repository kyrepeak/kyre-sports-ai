"""KYRE Streamlit Router V150 — CFB Game Total Monster compact dashboard.

Additive over frozen Router V149. Advances only exact College Football ->
Game Total to the compact presentation-only page while preserving V149
Over/Under V38, V148 Moneyline, NFL routes, every other certified market,
and all frozen Game Total calculations.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v77 as cfb_route_base
import streamlit_memory_lazy_router_v149 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V150 • CFB GAME TOTAL MONSTER COMPACT DASHBOARD"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v149"
CFB_SPORT_LABEL = "College Football"
GAME_TOTAL_MARKET = "Game Total"
ACTIVE_PAGE = "cfb_game_total_clean_page_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _game_total_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == CFB_SPORT_LABEL
        and str(st.session_state.get("ks_cfb_market_touch") or "") == GAME_TOTAL_MARKET
    )


def _render_cfb_game_total_v150(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    market = str(market or "")

    if sport == CFB_SPORT_LABEL and market != GAME_TOTAL_MARKET:
        # User changed CFB markets while V150 direct Game Total render was active.
        # Stop this stale rerun; the next rerun delegates to V149 normally.
        cfb_route_base._clear_fast_route_query()
        st.rerun()

    if sport != CFB_SPORT_LABEL or market != GAME_TOTAL_MARKET:
        return _ORIGINAL_RENDER_NFL(market)

    cfb_route_base._persist_fast_route_query()
    page = root._import(ACTIVE_PAGE)
    return page.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def _render_direct_cfb_game_total() -> None:
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    # Reuse the certified CFB selector/query behavior from the frozen fast path.
    root.st.selectbox = cfb_route_base._selectbox_v77
    root._render_nfl = _render_cfb_game_total_v150
    if "cfb_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("cfb_",)

    try:
        return root.render_app()
    finally:
        root.st.selectbox = original_selectbox
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    if not _game_total_route_active():
        cfb_route_base._restore_fast_route_from_query()
    if _game_total_route_active():
        return _render_direct_cfb_game_total()
    return prior.render_app()


__all__ = [
    "ACTIVE_PAGE",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "GAME_TOTAL_MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_game_total_route_active",
    "_render_cfb_game_total_v150",
    "_render_direct_cfb_game_total",
    "record_bootstrap_import_ms",
    "render_app",
]
