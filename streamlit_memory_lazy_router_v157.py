"""KYRE Streamlit Router V157 — CFB Game Total V161 production cache bust.

Additive over Router V156. V157 exists under a fresh module name so long-lived
Streamlit processes cannot reuse a stale cached V156 code object for exact
College Football -> Game Total. The exact V161 route owns its query/session
state and rendering locally; every non-target route delegates through V156.

Projection math, distribution math, Step-12 qualification, Top-5 ranking,
API/model behavior, and sportsbook projection influence remain unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v156 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V157 • CFB GAME TOTAL V161 CACHE BUST"
PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v156"
CFB_SPORT_LABEL = "College Football"
GAME_TOTAL_MARKET = "Game Total"
ACTIVE_PAGE = "cfb_game_total_clean_page_v12"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _query_value(name: str) -> str:
    try:
        value = st.query_params.get(name)
    except Exception:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""
    return str(value or "").strip()


def _game_total_route_active() -> bool:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    market = str(st.session_state.get("ks_cfb_market_touch") or "")
    return sport == CFB_SPORT_LABEL and market == GAME_TOTAL_MARKET


def _persist_game_total_route_query() -> None:
    """Persist exact V161 Game Total without any predecessor route helper."""
    try:
        if _query_value(ROUTE_QUERY_SPORT) != CFB_SPORT_LABEL:
            st.query_params[ROUTE_QUERY_SPORT] = CFB_SPORT_LABEL
        if _query_value(ROUTE_QUERY_MARKET) != GAME_TOTAL_MARKET:
            st.query_params[ROUTE_QUERY_MARKET] = GAME_TOTAL_MARKET
    except Exception:
        pass


def _clear_game_total_route_query() -> None:
    try:
        for key in (ROUTE_QUERY_SPORT, ROUTE_QUERY_MARKET):
            if key in st.query_params:
                del st.query_params[key]
    except Exception:
        pass


def _query_requests_game_total() -> bool:
    return (
        _query_value(ROUTE_QUERY_SPORT) == CFB_SPORT_LABEL
        and _query_value(ROUTE_QUERY_MARKET) == GAME_TOTAL_MARKET
    )


def _restore_game_total_route_from_query() -> bool:
    if not _query_requests_game_total():
        return False
    if _game_total_route_active():
        return True
    st.session_state["ks_sport_touch"] = CFB_SPORT_LABEL
    st.session_state["ks_cfb_market_touch"] = GAME_TOTAL_MARKET
    return True


def _render_production_heartbeat() -> None:
    st.markdown(
        f'<div data-testid="cfb-game-total-v161-heartbeat" '
        f'style="position:absolute;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none;font-size:1px">'
        f'{PRODUCTION_HEARTBEAT}</div>',
        unsafe_allow_html=True,
    )


def _render_exact_game_total_surface() -> None:
    """Render V161 directly without invoking cached predecessor route helpers."""
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


def _render_cfb_game_total_v157(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    market = str(market or "")
    if sport == CFB_SPORT_LABEL and market != GAME_TOTAL_MARKET:
        _clear_game_total_route_query()
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
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_clear_game_total_route_query",
    "_game_total_route_active",
    "_persist_game_total_route_query",
    "_query_requests_game_total",
    "_render_cfb_game_total_v157",
    "_render_direct_cfb_game_total",
    "_render_exact_game_total_surface",
    "_render_production_heartbeat",
    "_restore_game_total_route_from_query",
    "record_bootstrap_import_ms",
    "render_app",
]
