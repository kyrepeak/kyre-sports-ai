"""KYRE Streamlit Router V162 — CFB Game Total V166 Step 4 fresh multi-source activation.

Additive over frozen Router V161. Only exact College Football -> Game Total
advances to fresh Page V17. Every non-target route remains delegated through
V161. Projection math, probability/distribution math, model behavior, and
sportsbook projection influence remain unchanged.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v161 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V162 • CFB GAME TOTAL V166 STEP4 FRESH MULTISOURCE"
PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V166_STEP4_MULTISOURCE_ACTIVE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v161"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
GAME_TOTAL_MARKET = prior.GAME_TOTAL_MARKET
ACTIVE_PAGE = "cfb_game_total_clean_page_v17"
GAME_TOTAL_PAGE_PREFIX = prior.GAME_TOTAL_PAGE_PREFIX
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


def _render_exact_game_total_surface() -> None:
    original_page = prior.ACTIVE_PAGE
    original_heartbeat = prior.PRODUCTION_HEARTBEAT
    prior.ACTIVE_PAGE = ACTIVE_PAGE
    prior.PRODUCTION_HEARTBEAT = PRODUCTION_HEARTBEAT
    try:
        return prior._render_exact_game_total_surface()
    finally:
        prior.ACTIVE_PAGE = original_page
        prior.PRODUCTION_HEARTBEAT = original_heartbeat


def _render_cfb_game_total_v162(market: str) -> None:
    if market != GAME_TOTAL_MARKET:
        return prior._render_cfb_game_total_v161(market)
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
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRODUCTION_HEARTBEAT",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_clear_game_total_route_query",
    "_game_total_route_active",
    "_persist_game_total_route_query",
    "_purge_game_total_page_modules",
    "_render_cfb_game_total_v162",
    "_render_direct_cfb_game_total",
    "_render_exact_game_total_surface",
    "_restore_game_total_route_from_query",
    "record_bootstrap_import_ms",
    "render_app",
]
