"""KYRE Streamlit Router V176 — CFB Game Total sport navigation Step 1.

Additive over Router V175. Preserves the frozen navigation-escape behavior and
activates Page V29 only for the exact CFB Game Total route.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v173 as page_owner
import streamlit_memory_lazy_router_v175 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V176 • CFB SPORT NAV STEP 1 SHELL"
PRODUCTION_HEARTBEAT = (
    f"{prior.PRODUCTION_HEARTBEAT} • "
    "CFB_GAME_TOTAL_SPORT_NAV_STEP1_SHELL_ACTIVE"
)
FROZEN_ROUTER = "streamlit_memory_lazy_router_v175"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
GAME_TOTAL_MARKET = prior.GAME_TOTAL_MARKET
ACTIVE_PAGE = "cfb_game_total_clean_page_v29"
GAME_TOTAL_PAGE_PREFIX = prior.GAME_TOTAL_PAGE_PREFIX
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ROUTE_QUERY_SPORT = prior.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = prior.ROUTE_QUERY_MARKET
STEP6_CERT_QUERY_KEY = prior.STEP6_CERT_QUERY_KEY
STEP6_CERT_ROUTER_MARKER = prior.STEP6_CERT_ROUTER_MARKER
STEP6_VISUAL_PARITY_ROUTER_MARKER = prior.STEP6_VISUAL_PARITY_ROUTER_MARKER

SPORT_NAV_STEP1_ROUTER_MARKER = "CFB_GAME_TOTAL_SPORT_NAV_STEP1_SHELL_ACTIVE"


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


def _render_cfb_game_total_v176(market: str) -> None:
    if market != GAME_TOTAL_MARKET:
        return prior._render_cfb_game_total_v175(market)
    return _render_exact_game_total_surface()


def _render_direct_cfb_game_total() -> None:
    return _render_exact_game_total_surface()


def render_app() -> None:
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
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRODUCTION_HEARTBEAT",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_NAV_STEP1_ROUTER_MARKER",
    "STEP6_CERT_QUERY_KEY",
    "STEP6_CERT_ROUTER_MARKER",
    "STEP6_VISUAL_PARITY_ROUTER_MARKER",
    "_clear_game_total_route_query",
    "_explicit_non_game_total_route_selected",
    "_game_total_route_active",
    "_persist_game_total_route_query",
    "_purge_game_total_page_modules",
    "_render_cfb_game_total_v176",
    "_render_direct_cfb_game_total",
    "_render_exact_game_total_surface",
    "_render_step6_cert_surface",
    "_restore_game_total_route_from_query",
    "_step6_cert_requested",
    "_with_active_page",
    "record_bootstrap_import_ms",
    "render_app",
]
