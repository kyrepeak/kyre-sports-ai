"""KYRE Streamlit Router V160 — CFB Game Total V164 universal exact team logos.

Additive over permanently frozen Router V159. V160 advances only exact College
Football -> Game Total to fresh Page V15, preserving the V163 production baseline
and every non-target route through V159.

Projection math, distribution math, Step-12 qualification, Top-5 ranking,
API/model behavior, and sportsbook projection influence remain unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v159 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V160 • CFB GAME TOTAL V164 UNIVERSAL EXACT TEAM LOGOS"
PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V164_PRODUCTION_ACTIVE"
STEP1_PROFILE_HEARTBEAT = "CFB_GAME_TOTAL_STEP1_FAST_EXACT_PROFILE_ACTIVE"
LEGACY_V163_HEARTBEAT = "CFB_GAME_TOTAL_V163_PRODUCTION_ACTIVE"
LEGACY_V162_HEARTBEAT = "CFB_GAME_TOTAL_V162_PRODUCTION_ACTIVE"
LEGACY_V161_HEARTBEAT = "CFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v159"
CFB_SPORT_LABEL = "College Football"
GAME_TOTAL_MARKET = "Game Total"
ACTIVE_PAGE = "cfb_game_total_clean_page_v15"
GAME_TOTAL_PAGE_PREFIX = "cfb_game_total_clean_page_"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ROUTE_QUERY_SPORT = prior.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = prior.ROUTE_QUERY_MARKET


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _game_total_route_active() -> bool:
    return prior._game_total_route_active()


def _persist_game_total_route_query() -> None:
    return prior._persist_game_total_route_query()


def _clear_game_total_route_query() -> None:
    return prior._clear_game_total_route_query()


def _restore_game_total_route_from_query() -> bool:
    return prior._restore_game_total_route_from_query()


def _purge_game_total_page_modules() -> int:
    return prior._purge_game_total_page_modules()


def _render_production_heartbeat() -> None:
    st.markdown(
        f'<div data-testid="cfb-game-total-v164-heartbeat" '
        f'style="position:absolute;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none;font-size:1px">'
        f'{PRODUCTION_HEARTBEAT} • {STEP1_PROFILE_HEARTBEAT} • {LEGACY_V163_HEARTBEAT} • {LEGACY_V162_HEARTBEAT} • {LEGACY_V161_HEARTBEAT}</div>',
        unsafe_allow_html=True,
    )


def _render_exact_game_total_surface() -> None:
    st.set_page_config(
        page_title="Kyre Sports AI • CFB Game Total",
        page_icon="🏈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _persist_game_total_route_query()

    original_prefixes = root._ROUTE_MODULE_PREFIXES
    if "cfb_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("cfb_",)
    try:
        root._purge_route_modules_if_needed(
            root._route_token(CFB_SPORT_LABEL, GAME_TOTAL_MARKET)
        )
        _purge_game_total_page_modules()
        _render_production_heartbeat()
        page = root._import(ACTIVE_PAGE)
        return page.render_cfb_hub(
            GAME_TOTAL_MARKET,
            root.section_header,
            root.status_info,
            root.team_logo,
            root.h,
        )
    finally:
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def _render_cfb_game_total_v160(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    market = str(market or "")
    if sport == CFB_SPORT_LABEL and market != GAME_TOTAL_MARKET:
        _clear_game_total_route_query()
        st.rerun()
    if sport != CFB_SPORT_LABEL or market != GAME_TOTAL_MARKET:
        return prior._render_cfb_game_total_v159(market)
    return _render_exact_game_total_surface()


def _render_direct_cfb_game_total() -> None:
    return _render_exact_game_total_surface()


def render_app() -> None:
    if not _game_total_route_active():
        _restore_game_total_route_from_query()
    if _game_total_route_active():
        return _render_exact_game_total_surface()
    return prior.render_app()


__all__ = [
    "ACTIVE_PAGE",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "GAME_TOTAL_MARKET",
    "GAME_TOTAL_PAGE_PREFIX",
    "LEGACY_V161_HEARTBEAT",
    "LEGACY_V162_HEARTBEAT",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRODUCTION_HEARTBEAT",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP1_PROFILE_HEARTBEAT",
    "_clear_game_total_route_query",
    "_game_total_route_active",
    "_persist_game_total_route_query",
    "_purge_game_total_page_modules",
    "_render_cfb_game_total_v160",
    "_render_direct_cfb_game_total",
    "_render_exact_game_total_surface",
    "_render_production_heartbeat",
    "_restore_game_total_route_from_query",
    "record_bootstrap_import_ms",
    "render_app",
]
