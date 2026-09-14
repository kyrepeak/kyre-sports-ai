"""KYRE Streamlit Router V131 — NFL Moneyline cold-start fast route.

V131 preserves certified Router V130 for every non-Moneyline route while
allowing an already-active or query-restored NFL -> Moneyline session to start
without eagerly importing the historical V77-V130 router spine.

The active Moneyline page is additive V12, a performance-only wrapper over
frozen certified V11. All model/market safety ownership remains frozen.
"""
from __future__ import annotations

import importlib
import sys
from time import perf_counter
from typing import Any

import streamlit as st
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V131 • NFL MONEYLINE COLD-START FAST ROUTE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v130"
NFL_SPORT_LABEL = "NFL"
MONEYLINE_MARKET = "Moneyline"
ACTIVE_MONEYLINE_HUB = "nfl_moneyline_hub_v12"
ROUTE_QUERY_SPORT = "ks_nfl_sport"
ROUTE_QUERY_MARKET = "ks_nfl_market"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_ORIGINAL_SELECTBOX = root.st.selectbox
_FIRST_BOOTSTRAP_IMPORT_MS: float | None = None


def record_bootstrap_import_ms(value: float) -> None:
    global _FIRST_BOOTSTRAP_IMPORT_MS
    if _FIRST_BOOTSTRAP_IMPORT_MS is None:
        try:
            _FIRST_BOOTSTRAP_IMPORT_MS = max(0.0, float(value))
        except (TypeError, ValueError):
            _FIRST_BOOTSTRAP_IMPORT_MS = 0.0


def _load_prior():
    return importlib.import_module(FROZEN_ROUTER)


def _query_value(name: str) -> str:
    try:
        value = st.query_params.get(name)
    except Exception:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""
    return str(value or "").strip()


def _clear_fast_route_query() -> None:
    try:
        for key in (ROUTE_QUERY_SPORT, ROUTE_QUERY_MARKET):
            if key in st.query_params:
                del st.query_params[key]
    except Exception:
        pass


def _persist_fast_route_query() -> None:
    try:
        if _query_value(ROUTE_QUERY_SPORT) != NFL_SPORT_LABEL:
            st.query_params[ROUTE_QUERY_SPORT] = NFL_SPORT_LABEL
        if _query_value(ROUTE_QUERY_MARKET) != MONEYLINE_MARKET:
            st.query_params[ROUTE_QUERY_MARKET] = MONEYLINE_MARKET
    except Exception:
        pass


def _restore_fast_route_from_query() -> bool:
    current_sport = str(st.session_state.get("ks_sport_touch") or "").strip()
    current_market = str(st.session_state.get("ks_nfl_market_touch") or "").strip()
    if current_sport or current_market:
        return False
    if (
        _query_value(ROUTE_QUERY_SPORT) != NFL_SPORT_LABEL
        or _query_value(ROUTE_QUERY_MARKET) != MONEYLINE_MARKET
    ):
        return False
    st.session_state["ks_sport_touch"] = NFL_SPORT_LABEL
    st.session_state["ks_nfl_market_touch"] = MONEYLINE_MARKET
    return True


def _fast_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == NFL_SPORT_LABEL
        and str(st.session_state.get("ks_nfl_market_touch") or "") == MONEYLINE_MARKET
    )


def _selectbox_v131(label: Any, options: Any, *args: Any, **kwargs: Any):
    selected = _ORIGINAL_SELECTBOX(label, options, *args, **kwargs)
    if label == "🏟️ Sport" and str(selected) != NFL_SPORT_LABEL:
        _clear_fast_route_query()
    elif label == "🎯 NFL Market":
        if str(selected) == MONEYLINE_MARKET:
            _persist_fast_route_query()
        else:
            _clear_fast_route_query()
    return selected


def _render_nfl_v131(market: str) -> None:
    market = str(market or "Slate")
    if market != MONEYLINE_MARKET:
        raise RuntimeError("Router V131 direct handler is Moneyline only.")

    _persist_fast_route_query()
    legacy_chain_skipped = FROZEN_ROUTER not in sys.modules
    page_import_started = perf_counter()
    module = root._import(ACTIVE_MONEYLINE_HUB)
    page_import_ms = (perf_counter() - page_import_started) * 1000.0

    try:
        st.session_state["nfl_moneyline_cold_start_v131_last"] = {
            "version": MODEL_VERSION,
            "first_bootstrap_import_ms": _FIRST_BOOTSTRAP_IMPORT_MS,
            "active_page_import_ms": page_import_ms,
            "legacy_router_chain_skipped": legacy_chain_skipped,
            "restored_from_query": (
                _query_value(ROUTE_QUERY_SPORT) == NFL_SPORT_LABEL
                and _query_value(ROUTE_QUERY_MARKET) == MONEYLINE_MARKET
            ),
            "frozen_router": FROZEN_ROUTER,
            "active_page": ACTIVE_MONEYLINE_HUB,
            "sportsbook_projection_influence": 0.0,
            "stake_sizing_enabled": False,
        }
    except Exception:
        pass

    return module.render_nfl_hub(market)


def _render_direct_moneyline() -> None:
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    root.st.selectbox = _selectbox_v131
    root._render_nfl = _render_nfl_v131
    if "nfl_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("nfl_",)

    try:
        return root.render_app()
    finally:
        root.st.selectbox = original_selectbox
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    if not _fast_route_active():
        _restore_fast_route_from_query()
    if _fast_route_active():
        return _render_direct_moneyline()
    return _load_prior().render_app()


__all__ = [
    "ACTIVE_MONEYLINE_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "MONEYLINE_MARKET",
    "NFL_SPORT_LABEL",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_clear_fast_route_query",
    "_fast_route_active",
    "_load_prior",
    "_persist_fast_route_query",
    "_query_value",
    "_render_direct_moneyline",
    "_render_nfl_v131",
    "_restore_fast_route_from_query",
    "_selectbox_v131",
    "record_bootstrap_import_ms",
    "render_app",
]
