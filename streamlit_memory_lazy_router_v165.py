"""KYRE Streamlit Router V165 — V185 Step 6 production-safe activation hotfix.

Additive production hardening for the already-certified V185 Step 6 visual
surface. V165 avoids import-time dependence on V163/V164 cert-only attributes
by delegating the shared runtime route machinery to stable Router V162 and
implementing the Step 6 certification route locally.

Page V19, frozen V184 Step 6 data/model behavior, all non-target routes,
sportsbook projection influence 0.0%, and projection mutation OFF remain
unchanged.
"""
from __future__ import annotations

import importlib

import streamlit as st

import streamlit_memory_lazy_router_v162 as prior

MODEL_VERSION = (
    "KYRE STREAMLIT ROUTER V165 • V185 STEP6 PRODUCTION-SAFE VISUAL PARITY"
)
PRODUCTION_HEARTBEAT = (
    f"{prior.PRODUCTION_HEARTBEAT} • "
    "CFB_GAME_TOTAL_V184_STEP6_SCORING_CREATION_ACTIVE • "
    "CFB_GAME_TOTAL_V185_STEP6_VISUAL_PARITY_ACTIVE • "
    "CFB_GAME_TOTAL_V185_ROUTER_V165_PRODUCTION_HOTFIX_ACTIVE"
)
FROZEN_ROUTER = "streamlit_memory_lazy_router_v164"
SAFE_RUNTIME_DELEGATE = "streamlit_memory_lazy_router_v162"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
GAME_TOTAL_MARKET = prior.GAME_TOTAL_MARKET
ACTIVE_PAGE = "cfb_game_total_clean_page_v19"
GAME_TOTAL_PAGE_PREFIX = prior.GAME_TOTAL_PAGE_PREFIX
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ROUTE_QUERY_SPORT = prior.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = prior.ROUTE_QUERY_MARKET
STEP6_CERT_QUERY_KEY = "ks_cfb_step6_cert"
STEP6_CERT_ROUTER_MARKER = "CFB_GAME_TOTAL_V184_STEP6_CERT_ROUTER_ACTIVE"
STEP6_VISUAL_PARITY_ROUTER_MARKER = (
    "CFB_GAME_TOTAL_V185_STEP6_VISUAL_PARITY_ROUTER_ACTIVE"
)
STEP6_V165_PRODUCTION_HOTFIX_MARKER = (
    "CFB_GAME_TOTAL_V185_ROUTER_V165_PRODUCTION_HOTFIX_ACTIVE"
)


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
    try:
        raw = st.query_params.get(STEP6_CERT_QUERY_KEY)
    except Exception:
        return False
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip().casefold() in {"1", "true", "yes", "on"}


def _render_step6_cert_surface() -> None:
    st.set_page_config(
        page_title="Kyre Sports AI • CFB Game Total Step 6 Certification",
        page_icon="🏈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(
        f'<div data-testid="cfb-game-total-v185-step6-cert-heartbeat" '
        f'style="display:none!important">{PRODUCTION_HEARTBEAT} • '
        f'{STEP6_CERT_ROUTER_MARKER} • {STEP6_VISUAL_PARITY_ROUTER_MARKER} • '
        f'{STEP6_V165_PRODUCTION_HOTFIX_MARKER}</div>',
        unsafe_allow_html=True,
    )
    page = importlib.import_module(ACTIVE_PAGE)
    return page.render_step6_cert_surface()


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


def _render_cfb_game_total_v165(market: str) -> None:
    if market != GAME_TOTAL_MARKET:
        return prior._render_cfb_game_total_v162(market)
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
    "PRODUCTION_HEARTBEAT",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SAFE_RUNTIME_DELEGATE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP6_CERT_QUERY_KEY",
    "STEP6_CERT_ROUTER_MARKER",
    "STEP6_VISUAL_PARITY_ROUTER_MARKER",
    "STEP6_V165_PRODUCTION_HOTFIX_MARKER",
    "_clear_game_total_route_query",
    "_game_total_route_active",
    "_persist_game_total_route_query",
    "_purge_game_total_page_modules",
    "_render_cfb_game_total_v165",
    "_render_direct_cfb_game_total",
    "_render_exact_game_total_surface",
    "_render_step6_cert_surface",
    "_restore_game_total_route_from_query",
    "_step6_cert_requested",
    "record_bootstrap_import_ms",
    "render_app",
]
