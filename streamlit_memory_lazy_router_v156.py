"""KYRE Streamlit Router V156 — CFB Game Total V161 activation.

Additive over frozen Router V155. V156 advances only exact College Football ->
Game Total from Clean Page V10 to V11. Every other certified route remains
delegated through frozen V155 unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v77 as cfb_route_base
import streamlit_memory_lazy_router_v155 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V156 • CFB GAME TOTAL V161"
PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v155"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
GAME_TOTAL_MARKET = prior.GAME_TOTAL_MARKET
ACTIVE_PAGE = "cfb_game_total_clean_page_v11"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _game_total_route_active() -> bool:
    return prior._game_total_route_active()


def _persist_game_total_route_query() -> None:
    return prior._persist_game_total_route_query()


def _query_requests_game_total() -> bool:
    return prior._query_requests_game_total()


def _restore_game_total_route_from_query() -> bool:
    return prior._restore_game_total_route_from_query()


def _render_production_heartbeat() -> None:
    st.markdown(
        f'<div data-testid="cfb-game-total-v161-heartbeat" '
        f'style="position:absolute;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none;font-size:1px">'
        f'{PRODUCTION_HEARTBEAT}</div>',
        unsafe_allow_html=True,
    )


def _render_exact_game_total_surface() -> None:
    """Render V161 Game Total directly while preserving V155 route isolation."""
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


def _render_cfb_game_total_v156(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    market = str(market or "")
    if sport == CFB_SPORT_LABEL and market != GAME_TOTAL_MARKET:
        cfb_route_base._clear_fast_route_query()
        st.rerun()
    if sport != CFB_SPORT_LABEL or market != GAME_TOTAL_MARKET:
        return _ORIGINAL_RENDER_NFL(market)
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
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRODUCTION_HEARTBEAT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_game_total_route_active",
    "_persist_game_total_route_query",
    "_query_requests_game_total",
    "_render_cfb_game_total_v156",
    "_render_direct_cfb_game_total",
    "_render_exact_game_total_surface",
    "_render_production_heartbeat",
    "_restore_game_total_route_from_query",
    "record_bootstrap_import_ms",
    "render_app",
]
