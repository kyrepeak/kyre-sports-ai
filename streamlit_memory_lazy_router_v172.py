"""KYRE Streamlit Router V172 — CFB Game Total visual redesign Step 4.

Additive over Router V171. Only the normal College Football Game Total route
advances from Page V26 to Page V27. Frozen certification behavior remains
delegated through the prior certified route.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v171 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V172 • CFB GAME TOTAL VISUAL REDESIGN STEP 4 TEAM EVIDENCE"
PRODUCTION_HEARTBEAT = (
    f"{prior.PRODUCTION_HEARTBEAT} • "
    "CFB_GAME_TOTAL_VISUAL_REDESIGN_STEP4_TEAM_EVIDENCE_ACTIVE"
)
FROZEN_ROUTER = "streamlit_memory_lazy_router_v171"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
GAME_TOTAL_MARKET = prior.GAME_TOTAL_MARKET
ACTIVE_PAGE = "cfb_game_total_clean_page_v27"
GAME_TOTAL_PAGE_PREFIX = prior.GAME_TOTAL_PAGE_PREFIX
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ROUTE_QUERY_SPORT = prior.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = prior.ROUTE_QUERY_MARKET
STEP6_CERT_QUERY_KEY = prior.STEP6_CERT_QUERY_KEY
STEP6_CERT_ROUTER_MARKER = prior.STEP6_CERT_ROUTER_MARKER
STEP6_VISUAL_PARITY_ROUTER_MARKER = prior.STEP6_VISUAL_PARITY_ROUTER_MARKER

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

def _with_active_page(callback):
    original_page = prior.ACTIVE_PAGE
    original_heartbeat = prior.PRODUCTION_HEARTBEAT
    prior.ACTIVE_PAGE = ACTIVE_PAGE
    prior.PRODUCTION_HEARTBEAT = PRODUCTION_HEARTBEAT
    try:
        return callback()
    finally:
        prior.ACTIVE_PAGE = original_page
        prior.PRODUCTION_HEARTBEAT = original_heartbeat

def _render_step6_cert_surface() -> None:
    return prior._render_step6_cert_surface()

def _render_exact_game_total_surface() -> None:
    return _with_active_page(prior._render_exact_game_total_surface)

def _render_cfb_game_total_v172(market: str) -> None:
    if market != GAME_TOTAL_MARKET:
        return prior._render_cfb_game_total_v171(market)
    return _render_exact_game_total_surface()

def _render_direct_cfb_game_total() -> None:
    return _render_exact_game_total_surface()

def render_app() -> None:
    if not _game_total_route_active():
        _restore_game_total_route_from_query()
    if _game_total_route_active():
        if _step6_cert_requested():
            return _render_step6_cert_surface()
        return _render_exact_game_total_surface()
    return prior.render_app()

__all__ = [
    "ACTIVE_PAGE","CFB_SPORT_LABEL","FROZEN_ROUTER","GAME_TOTAL_MARKET",
    "GAME_TOTAL_PAGE_PREFIX","MAY_MODIFY_PROJECTION","MODEL_VERSION",
    "PRODUCTION_HEARTBEAT","ROUTE_QUERY_MARKET","ROUTE_QUERY_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE","STEP6_CERT_QUERY_KEY",
    "STEP6_CERT_ROUTER_MARKER","STEP6_VISUAL_PARITY_ROUTER_MARKER",
    "_clear_game_total_route_query","_game_total_route_active",
    "_persist_game_total_route_query","_purge_game_total_page_modules",
    "_render_cfb_game_total_v172","_render_direct_cfb_game_total",
    "_render_exact_game_total_surface","_render_step6_cert_surface",
    "_restore_game_total_route_from_query","_step6_cert_requested",
    "record_bootstrap_import_ms","render_app",
]
