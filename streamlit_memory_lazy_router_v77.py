"""KYRE Streamlit Router V77 — CFB O/U cold-start fast route.

Step 6 of the College Football Over/Under performance work.

V77 preserves certified Router V76 behavior but removes the historical router
chain from the import path when College Football -> Over/Under is already the
active Streamlit route. The frozen V76 chain is imported lazily only when a
non-fast route needs it.

The active CFB O/U page remains Clean Page V35. No schedule, market, team-data,
projection, ranking, qualification, selection, or sportsbook semantics change.
"""
from __future__ import annotations

import importlib
import sys
from time import perf_counter
from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V77 • CFB O/U COLD-START FAST ROUTE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v76"
CFB_SPORT_LABEL = "College Football"
CFB_MARKETS = ("Moneyline", "Over/Under", "Game Total")
OVER_UNDER_MARKET = "Over/Under"
ACTIVE_PAGE = "cfb_over_under_clean_page_v35"

_ORIGINAL_SELECTBOX = root.st.selectbox
_ORIGINAL_RENDER_NFL = root._render_nfl
_FIRST_BOOTSTRAP_IMPORT_MS: float | None = None


def record_bootstrap_import_ms(value: float) -> None:
    """Record the first process-level active-router import cost once."""
    global _FIRST_BOOTSTRAP_IMPORT_MS
    if _FIRST_BOOTSTRAP_IMPORT_MS is None:
        try:
            _FIRST_BOOTSTRAP_IMPORT_MS = max(0.0, float(value))
        except (TypeError, ValueError):
            _FIRST_BOOTSTRAP_IMPORT_MS = 0.0


def _load_prior():
    """Import frozen Router V76 only when the fast CFB O/U route is unavailable."""
    return importlib.import_module(FROZEN_ROUTER)


def _fast_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == CFB_SPORT_LABEL
        and str(st.session_state.get("ks_cfb_market_touch") or "") == OVER_UNDER_MARKET
    )


def _selectbox_v77(label: Any, options: Any, *args: Any, **kwargs: Any):
    if label == "🏟️ Sport":
        choices = list(options)
        if CFB_SPORT_LABEL not in choices:
            choices.append(CFB_SPORT_LABEL)
        return _ORIGINAL_SELECTBOX(label, choices, *args, **kwargs)

    if (
        label == "🎯 NFL Market"
        and str(st.session_state.get("ks_sport_touch") or "") == CFB_SPORT_LABEL
    ):
        if str(st.session_state.get("ks_cfb_market_touch") or "") not in CFB_MARKETS:
            st.session_state.pop("ks_cfb_market_touch", None)

        clean_kwargs = dict(kwargs)
        clean_kwargs.pop("key", None)
        clean_kwargs.pop("index", None)
        return _ORIGINAL_SELECTBOX(
            "🎯 CFB Market",
            list(CFB_MARKETS),
            *args,
            key="ks_cfb_market_touch",
            **clean_kwargs,
        )

    return _ORIGINAL_SELECTBOX(label, options, *args, **kwargs)


def _render_cfb_ou_direct(market: str) -> None:
    if (
        str(st.session_state.get("ks_sport_touch") or "") != CFB_SPORT_LABEL
        or market != OVER_UNDER_MARKET
    ):
        return _ORIGINAL_RENDER_NFL(market)

    legacy_chain_skipped = FROZEN_ROUTER not in sys.modules
    page_import_started = perf_counter()
    mod = root._import(ACTIVE_PAGE)
    page_import_ms = (perf_counter() - page_import_started) * 1000.0

    try:
        st.session_state["cfb_ou_cold_start_v1_last"] = {
            "version": MODEL_VERSION,
            "first_bootstrap_import_ms": _FIRST_BOOTSTRAP_IMPORT_MS,
            "active_page_import_ms": page_import_ms,
            "legacy_router_chain_skipped": legacy_chain_skipped,
            "frozen_router": FROZEN_ROUTER,
            "active_page": ACTIVE_PAGE,
            "projection_weight": 0.0,
            "may_modify_projection": False,
        }
    except Exception:
        pass

    bootstrap_ms = _FIRST_BOOTSTRAP_IMPORT_MS
    bootstrap_text = "n/a" if bootstrap_ms is None else f"{bootstrap_ms:.1f} ms"
    st.caption(
        "⚡ CFB O/U COLD PATH V1 • "
        f"bootstrap router import {bootstrap_text} • "
        f"active-page import {page_import_ms:.1f} ms • "
        f"historical router chain {'SKIPPED' if legacy_chain_skipped else 'already loaded'} • "
        "projection math unchanged"
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

    root.st.selectbox = _selectbox_v77
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
    if _fast_route_active():
        return _render_direct_cfb_ou()
    return _load_prior().render_app()


__all__ = [
    "ACTIVE_PAGE",
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "OVER_UNDER_MARKET",
    "_fast_route_active",
    "_load_prior",
    "_render_cfb_ou_direct",
    "_render_direct_cfb_ou",
    "_selectbox_v77",
    "record_bootstrap_import_ms",
    "render_app",
]
