"""KYRE Streamlit Router V152 — CFB Game Total production rebuild.

Additive over frozen Router V151. V152 advances only exact College Football ->
Game Total to the current V152 clean page while every other route delegates to
V151. The exact Game Total route exposes a production heartbeat so stale
Streamlit releases fail verification instead of passing on a generic HTTP 200.

Frozen Game Total Step-11/Step-12 calculations remain untouched. Sportsbook
projection influence stays 0.0%.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v77 as cfb_route_base
import streamlit_memory_lazy_router_v151 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V152 • CFB GAME TOTAL PRODUCTION REBUILD"
PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v151"
CFB_SPORT_LABEL = "College Football"
GAME_TOTAL_MARKET = "Game Total"
ACTIVE_PAGE = "cfb_game_total_clean_page_v4"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _game_total_route_active() -> bool:
    return prior._game_total_route_active()


def _persist_game_total_route_query() -> None:
    return prior._persist_game_total_route_query()


def _restore_game_total_route_from_query() -> bool:
    return prior._restore_game_total_route_from_query()


def _render_production_heartbeat() -> None:
    st.markdown(
        f'<div data-testid="cfb-game-total-v152-heartbeat" '
        f'style="font-size:.58rem;font-weight:800;color:#a7b6c5;margin:0 0 4px 2px">'
        f'{PRODUCTION_HEARTBEAT}</div>',
        unsafe_allow_html=True,
    )


def _render_cfb_game_total_v152(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    market = str(market or "")

    if sport == CFB_SPORT_LABEL and market != GAME_TOTAL_MARKET:
        cfb_route_base._clear_fast_route_query()
        st.rerun()

    if sport != CFB_SPORT_LABEL or market != GAME_TOTAL_MARKET:
        return _ORIGINAL_RENDER_NFL(market)

    _persist_game_total_route_query()
    _render_production_heartbeat()
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

    root.st.selectbox = cfb_route_base._selectbox_v77
    root._render_nfl = _render_cfb_game_total_v152
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
        _restore_game_total_route_from_query()
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
    "PRODUCTION_HEARTBEAT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_game_total_route_active",
    "_persist_game_total_route_query",
    "_render_cfb_game_total_v152",
    "_render_direct_cfb_game_total",
    "_render_production_heartbeat",
    "_restore_game_total_route_from_query",
    "record_bootstrap_import_ms",
    "render_app",
]
