"""KYRE Streamlit Router V180 — dropdown category routing Step 3.

Additive over Router V179. Consumes validated sport+market dropdown jumps and
writes only the existing Streamlit session-state route keys.
"""
from __future__ import annotations

import streamlit as st

import cfb_hub_v1 as cfb
import streamlit_memory_lazy_router_v1 as base
import streamlit_memory_lazy_router_v173 as page_owner
import streamlit_memory_lazy_router_v179 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V180 • SPORT DROPDOWN STEP 3 FUNCTIONAL"
PRODUCTION_HEARTBEAT = (
    f"{prior.PRODUCTION_HEARTBEAT} • "
    "CFB_GAME_TOTAL_SPORT_DROPDOWN_STEP3_FUNCTIONAL_ACTIVE"
)
FROZEN_ROUTER = "streamlit_memory_lazy_router_v179"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
GAME_TOTAL_MARKET = prior.GAME_TOTAL_MARKET
ACTIVE_PAGE = "cfb_game_total_clean_page_v33"
GAME_TOTAL_PAGE_PREFIX = prior.GAME_TOTAL_PAGE_PREFIX
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ROUTE_QUERY_SPORT = prior.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = prior.ROUTE_QUERY_MARKET
STEP6_CERT_QUERY_KEY = prior.STEP6_CERT_QUERY_KEY
STEP6_CERT_ROUTER_MARKER = prior.STEP6_CERT_ROUTER_MARKER
STEP6_VISUAL_PARITY_ROUTER_MARKER = prior.STEP6_VISUAL_PARITY_ROUTER_MARKER
SPORT_DROPDOWN_STEP3_ROUTER_MARKER = "CFB_GAME_TOTAL_SPORT_DROPDOWN_STEP3_FUNCTIONAL_ACTIVE"

SPORT_JUMP_QUERY_KEY = "ks_jump_sport"
MARKET_JUMP_QUERY_KEY = "ks_jump_market"
SPORT_TARGETS = {
    "NFL": "NFL",
    "CFB": CFB_SPORT_LABEL,
    "MLB": "MLB",
    "WNBA": "WNBA",
}
SPORT_MARKETS = {
    "NFL": tuple(base.NFL_MARKETS),
    "CFB": tuple(cfb.CFB_MARKETS),
    "MLB": tuple(base.MLB_MARKETS),
    "WNBA": tuple(base.WNBA_MARKETS),
}
SPORT_MARKET_KEYS = {
    "NFL": "ks_nfl_market_touch",
    "CFB": "ks_cfb_market_touch",
    "MLB": "ks_mlb_market_touch",
    "WNBA": "ks_wnba_market_touch",
}


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


def _step6_cert_requested() -> bool:
    return prior._step6_cert_requested()


def _explicit_non_game_total_route_selected() -> bool:
    return prior._explicit_non_game_total_route_selected()


def _query_value(key: str) -> str:
    raw = st.query_params.get(key)
    if isinstance(raw, list):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _apply_category_jump(code: str, market: str) -> bool:
    code = str(code or "").strip().upper()
    market = str(market or "").strip()

    sport = SPORT_TARGETS.get(code)
    allowed = SPORT_MARKETS.get(code)
    market_key = SPORT_MARKET_KEYS.get(code)

    if not sport or not allowed or not market_key or market not in allowed:
        return False

    st.session_state["ks_sport_touch"] = sport
    st.session_state[market_key] = market

    if code == "MLB":
        st.session_state.pop("ks_mlb_live_odds_route", None)

    return True


def _consume_category_jump_query() -> bool:
    code = _query_value(SPORT_JUMP_QUERY_KEY).upper()
    market = _query_value(MARKET_JUMP_QUERY_KEY)

    if not market:
        return False

    if not _apply_category_jump(code, market):
        return False

    for key in (SPORT_JUMP_QUERY_KEY, MARKET_JUMP_QUERY_KEY):
        try:
            del st.query_params[key]
        except Exception:
            pass

    st.rerun()
    return True


def _consume_sport_jump_query() -> bool:
    # Category jumps own the two-key form. Otherwise preserve frozen Step-2 sport jump.
    if _query_value(MARKET_JUMP_QUERY_KEY):
        return False
    return prior._consume_sport_jump_query()


def _with_active_page(callback):
    original_page = page_owner.ACTIVE_PAGE
    original_heartbeat = page_owner.PRODUCTION_HEARTBEAT
    page_owner.ACTIVE_PAGE = ACTIVE_PAGE
    page_owner.PRODUCTION_HEARTBEAT = PRODUCTION_HEARTBEAT
    try:
        return callback()
    finally:
        page_owner.ACTIVE_PAGE = original_page
        page_owner.PRODUCTION_HEARTBEAT = original_heartbeat


def _render_step6_cert_surface() -> None:
    return prior._render_step6_cert_surface()


def _render_exact_game_total_surface() -> None:
    return _with_active_page(prior._render_exact_game_total_surface)


def _render_cfb_game_total_v180(market: str) -> None:
    if market != GAME_TOTAL_MARKET:
        return prior._render_cfb_game_total_v179(market)
    return _render_exact_game_total_surface()


def _render_direct_cfb_game_total() -> None:
    return _render_exact_game_total_surface()


def render_app() -> None:
    if _consume_category_jump_query():
        return

    if _consume_sport_jump_query():
        return

    if _explicit_non_game_total_route_selected():
        _clear_game_total_route_query()
        return prior.render_app()

    if not _game_total_route_active():
        _restore_game_total_route_from_query()

    if _game_total_route_active():
        if _step6_cert_requested():
            return _render_step6_cert_surface()
        return _render_exact_game_total_surface()

    return prior.render_app()


__all__ = [
    "ACTIVE_PAGE","CFB_SPORT_LABEL","FROZEN_ROUTER","GAME_TOTAL_MARKET",
    "GAME_TOTAL_PAGE_PREFIX","MARKET_JUMP_QUERY_KEY","MAY_MODIFY_PROJECTION",
    "MODEL_VERSION","PRODUCTION_HEARTBEAT","ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT","SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_DROPDOWN_STEP3_ROUTER_MARKER","SPORT_JUMP_QUERY_KEY",
    "SPORT_MARKETS","SPORT_MARKET_KEYS","SPORT_TARGETS",
    "STEP6_CERT_QUERY_KEY","STEP6_CERT_ROUTER_MARKER",
    "STEP6_VISUAL_PARITY_ROUTER_MARKER","_apply_category_jump",
    "_clear_game_total_route_query","_consume_category_jump_query",
    "_consume_sport_jump_query","_explicit_non_game_total_route_selected",
    "_game_total_route_active","_persist_game_total_route_query",
    "_purge_game_total_page_modules","_query_value",
    "_render_cfb_game_total_v180","_render_direct_cfb_game_total",
    "_render_exact_game_total_surface","_render_step6_cert_surface",
    "_restore_game_total_route_from_query","_step6_cert_requested",
    "_with_active_page","record_bootstrap_import_ms","render_app",
]
