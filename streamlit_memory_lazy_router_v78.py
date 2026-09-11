"""KYRE Streamlit Router V78 — exact CFB O/U team logos.

Additive wrapper over certified Router V77. The cold-start fast route and query
state behavior remain unchanged; only the active College Football -> Over/Under
page advances from Clean Page V35 to Clean Page V36.
"""
from __future__ import annotations

from time import perf_counter
from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v77 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V78 • CFB O/U EXACT TEAM LOGOS"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v77"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
CFB_MARKETS = tuple(prior.CFB_MARKETS)
OVER_UNDER_MARKET = prior.OVER_UNDER_MARKET
ACTIVE_PAGE = "cfb_over_under_clean_page_v36"
ROUTE_QUERY_SPORT = prior.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = prior.ROUTE_QUERY_MARKET

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_cfb_ou_direct(market: str) -> None:
    if (
        str(st.session_state.get("ks_sport_touch") or "") != CFB_SPORT_LABEL
        or market != OVER_UNDER_MARKET
    ):
        return _ORIGINAL_RENDER_NFL(market)

    prior._persist_fast_route_query()
    page_import_started = perf_counter()
    mod = root._import(ACTIVE_PAGE)
    page_import_ms = (perf_counter() - page_import_started) * 1000.0

    try:
        st.session_state["cfb_ou_cold_start_v1_last"] = {
            "version": MODEL_VERSION,
            "first_bootstrap_import_ms": prior._FIRST_BOOTSTRAP_IMPORT_MS,
            "active_page_import_ms": page_import_ms,
            "legacy_router_chain_skipped": True,
            "restored_from_query": (
                prior._query_value(ROUTE_QUERY_SPORT) == CFB_SPORT_LABEL
                and prior._query_value(ROUTE_QUERY_MARKET) == OVER_UNDER_MARKET
            ),
            "frozen_router": FROZEN_ROUTER,
            "active_page": ACTIVE_PAGE,
            "projection_weight": 0.0,
            "may_modify_projection": False,
        }
    except Exception:
        pass

    bootstrap_ms = prior._FIRST_BOOTSTRAP_IMPORT_MS
    bootstrap_text = "n/a" if bootstrap_ms is None else f"{bootstrap_ms:.1f} ms"
    st.caption(
        "⚡ CFB O/U COLD PATH V1 • "
        f"bootstrap router import {bootstrap_text} • "
        f"active-page import {page_import_ms:.1f} ms • "
        "historical router chain SKIPPED • projection math unchanged"
    )

    mod.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def _render_direct_cfb_ou() -> None:
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    root.st.selectbox = prior._selectbox_v77
    root._render_nfl = _render_cfb_ou_direct
    if "cfb_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("cfb_",)

    try:
        root.render_app()
    finally:
        root.st.selectbox = original_selectbox
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    if not prior._fast_route_active():
        prior._restore_fast_route_from_query()
    if prior._fast_route_active():
        return _render_direct_cfb_ou()
    return prior._load_prior().render_app()


__all__ = [
    "ACTIVE_PAGE",
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "OVER_UNDER_MARKET",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "_render_cfb_ou_direct",
    "_render_direct_cfb_ou",
    "record_bootstrap_import_ms",
    "render_app",
]
