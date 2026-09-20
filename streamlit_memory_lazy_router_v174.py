"""KYRE Streamlit Router V174 — CFB Game Total page cleanup Step 1.

Presentation-only router successor to V173. V174 suppresses the legacy visible
production-heartbeat wall on the CFB Game Total route while preserving all
heartbeat constants, route ownership, certified Page V28 presentation, and
model/data behavior.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v160 as visible_heartbeat_owner
import streamlit_memory_lazy_router_v173 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V174 • CFB GAME TOTAL PAGE CLEANUP STEP 1 HIDE DEBUG WALL"
PRODUCTION_HEARTBEAT = (
    f"{prior.PRODUCTION_HEARTBEAT} • "
    "CFB_GAME_TOTAL_PAGE_CLEANUP_STEP1_DEBUG_WALL_HIDDEN"
)
FROZEN_ROUTER = "streamlit_memory_lazy_router_v173"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
GAME_TOTAL_MARKET = prior.GAME_TOTAL_MARKET
ACTIVE_PAGE = prior.ACTIVE_PAGE
GAME_TOTAL_PAGE_PREFIX = prior.GAME_TOTAL_PAGE_PREFIX
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ROUTE_QUERY_SPORT = prior.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = prior.ROUTE_QUERY_MARKET
STEP6_CERT_QUERY_KEY = prior.STEP6_CERT_QUERY_KEY
STEP6_CERT_ROUTER_MARKER = prior.STEP6_CERT_ROUTER_MARKER
STEP6_VISUAL_PARITY_ROUTER_MARKER = prior.STEP6_VISUAL_PARITY_ROUTER_MARKER

PAGE_CLEANUP_STEP1_MARKER = "CFB_GAME_TOTAL_PAGE_CLEANUP_STEP1_DEBUG_WALL_HIDDEN"


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


def _hide_legacy_visible_heartbeat(callback, *args, **kwargs):
    original = visible_heartbeat_owner._render_production_heartbeat
    visible_heartbeat_owner._render_production_heartbeat = lambda: None
    try:
        return callback(*args, **kwargs)
    finally:
        visible_heartbeat_owner._render_production_heartbeat = original


def _render_step6_cert_surface() -> None:
    return prior._render_step6_cert_surface()


def _render_exact_game_total_surface() -> None:
    return _hide_legacy_visible_heartbeat(prior._render_exact_game_total_surface)


def _render_cfb_game_total_v174(market: str) -> None:
    if market != GAME_TOTAL_MARKET:
        return prior._render_cfb_game_total_v173(market)
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
    "ACTIVE_PAGE",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "GAME_TOTAL_MARKET",
    "GAME_TOTAL_PAGE_PREFIX",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PAGE_CLEANUP_STEP1_MARKER",
    "PRODUCTION_HEARTBEAT",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP6_CERT_QUERY_KEY",
    "STEP6_CERT_ROUTER_MARKER",
    "STEP6_VISUAL_PARITY_ROUTER_MARKER",
    "_clear_game_total_route_query",
    "_game_total_route_active",
    "_hide_legacy_visible_heartbeat",
    "_persist_game_total_route_query",
    "_purge_game_total_page_modules",
    "_render_cfb_game_total_v174",
    "_render_direct_cfb_game_total",
    "_render_exact_game_total_surface",
    "_render_step6_cert_surface",
    "_restore_game_total_route_from_query",
    "_step6_cert_requested",
    "record_bootstrap_import_ms",
    "render_app",
]
