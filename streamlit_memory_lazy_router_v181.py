"""KYRE Streamlit Router V181 — live sport-nav ownership fix.

Fixes the production bug where nested additive routers V176-V180 repeatedly
overwrote the requested ACTIVE_PAGE while forwarding to older wrappers. V181
keeps the proven V180 sport/category jump logic, but sends the exact CFB Game
Total render directly to the original V160 render owner with Page V33 selected.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v160 as render_owner
import streamlit_memory_lazy_router_v180 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V181 • LIVE SPORT NAV OWNERSHIP FIX"
PRODUCTION_HEARTBEAT = (
    f"{prior.PRODUCTION_HEARTBEAT} • "
    "CFB_GAME_TOTAL_LIVE_SPORT_NAV_OWNERSHIP_FIX_V181_ACTIVE"
)
FROZEN_ROUTER = "streamlit_memory_lazy_router_v180"
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
LIVE_SPORT_NAV_OWNERSHIP_FIX_MARKER = "CFB_GAME_TOTAL_LIVE_SPORT_NAV_OWNERSHIP_FIX_V181_ACTIVE"


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


def _step6_cert_requested() -> bool:
    return prior._step6_cert_requested()


def _explicit_non_game_total_route_selected() -> bool:
    return prior._explicit_non_game_total_route_selected()


def _consume_category_jump_query() -> bool:
    return prior._consume_category_jump_query()


def _consume_sport_jump_query() -> bool:
    return prior._consume_sport_jump_query()


def _render_step6_cert_surface() -> None:
    return prior._render_step6_cert_surface()


def _render_exact_game_total_surface() -> None:
    original_page = render_owner.ACTIVE_PAGE
    original_heartbeat = render_owner.PRODUCTION_HEARTBEAT
    render_owner.ACTIVE_PAGE = ACTIVE_PAGE
    render_owner.PRODUCTION_HEARTBEAT = PRODUCTION_HEARTBEAT
    try:
        return render_owner._render_exact_game_total_surface()
    finally:
        render_owner.ACTIVE_PAGE = original_page
        render_owner.PRODUCTION_HEARTBEAT = original_heartbeat


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
    "ACTIVE_PAGE",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "GAME_TOTAL_MARKET",
    "GAME_TOTAL_PAGE_PREFIX",
    "LIVE_SPORT_NAV_OWNERSHIP_FIX_MARKER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRODUCTION_HEARTBEAT",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP6_CERT_QUERY_KEY",
    "STEP6_CERT_ROUTER_MARKER",
    "STEP6_VISUAL_PARITY_ROUTER_MARKER",
    "_clear_game_total_route_query",
    "_consume_category_jump_query",
    "_consume_sport_jump_query",
    "_explicit_non_game_total_route_selected",
    "_game_total_route_active",
    "_render_direct_cfb_game_total",
    "_render_exact_game_total_surface",
    "_render_step6_cert_surface",
    "_restore_game_total_route_from_query",
    "_step6_cert_requested",
    "record_bootstrap_import_ms",
    "render_app",
]
