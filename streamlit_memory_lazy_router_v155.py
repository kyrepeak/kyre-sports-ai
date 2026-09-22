"""KYRE Streamlit Router V155 — CFB Game Total V160 visual-parity activation.

Additive over frozen Router V154. V155 advances only exact College Football ->
Game Total to Clean Page V10. CFB Over/Under V39 and every other certified route
remain delegated through frozen V154 unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v77 as cfb_route_base
import streamlit_memory_lazy_router_v154 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V155 • CFB GAME TOTAL V160 VISUAL PARITY"
PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V160_PRODUCTION_ACTIVE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v154"
CFB_SPORT_LABEL = "College Football"
GAME_TOTAL_MARKET = "Game Total"
ACTIVE_PAGE = "cfb_game_total_clean_page_v10"
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


def _persist_game_total_route_query() -> None:
    """Persist exact CFB Game Total without reusing V77's O/U-only helper."""
    try:
        if cfb_route_base._query_value(cfb_route_base.ROUTE_QUERY_SPORT) != CFB_SPORT_LABEL:
            st.query_params[cfb_route_base.ROUTE_QUERY_SPORT] = CFB_SPORT_LABEL
        if cfb_route_base._query_value(cfb_route_base.ROUTE_QUERY_MARKET) != GAME_TOTAL_MARKET:
            st.query_params[cfb_route_base.ROUTE_QUERY_MARKET] = GAME_TOTAL_MARKET
    except Exception:
        pass


def _query_requests_game_total() -> bool:
    return (
        cfb_route_base._query_value(cfb_route_base.ROUTE_QUERY_SPORT) == CFB_SPORT_LABEL
        and cfb_route_base._query_value(cfb_route_base.ROUTE_QUERY_MARKET) == GAME_TOTAL_MARKET
    )


def _restore_game_total_route_from_query() -> bool:
    current_sport = str(st.session_state.get("ks_sport_touch") or "").strip()
    current_market = str(st.session_state.get("ks_cfb_market_touch") or "").strip()
    if current_sport or current_market:
        return False
    if not _query_requests_game_total():
        return False
    st.session_state["ks_sport_touch"] = CFB_SPORT_LABEL
    st.session_state["ks_cfb_market_touch"] = GAME_TOTAL_MARKET
    return True


def _render_production_heartbeat() -> None:
    # Keep the immutable activation marker available to browser certification
    # without adding any visible chrome to the exact Monster target surface.
    # Playwright treats an opacity-0 element with a non-empty box as visible,
    # while users cannot see the 1px marker.
    st.markdown(
        f'<div data-testid="cfb-game-total-v160-heartbeat" '
        f'style="position:absolute;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none;font-size:1px">'
        f'{PRODUCTION_HEARTBEAT}</div>',
        unsafe_allow_html=True,
    )


def _render_cfb_game_total_v155(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    market = str(market or "")

    if sport == CFB_SPORT_LABEL and market != GAME_TOTAL_MARKET:
        cfb_route_base._clear_fast_route_query()
        st.rerun()

    if sport != CFB_SPORT_LABEL or market != GAME_TOTAL_MARKET:
        return _ORIGINAL_RENDER_NFL(market)

    return _render_exact_game_total_surface()


def _render_exact_game_total_surface() -> None:
    """Render Game Total as the page itself, not inside the generic router shell."""
    st.set_page_config(
        page_title="Monster Sports Intelligence • CFB Game Total",
        page_icon="👾",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _persist_game_total_route_query()

    # Preserve the memory-safe route transition behavior while keeping the
    # generic KYRE shell/selectors off the final Game Total surface.
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


def _render_direct_cfb_game_total() -> None:
    # Compatibility alias retained for frozen activation tests and callers.
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
    "_render_cfb_game_total_v155",
    "_render_direct_cfb_game_total",
    "_render_exact_game_total_surface",
    "_render_production_heartbeat",
    "_restore_game_total_route_from_query",
    "record_bootstrap_import_ms",
    "render_app",
]
