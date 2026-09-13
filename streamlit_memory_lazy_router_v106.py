"""KYRE Streamlit Router V106 — NFL Rushing Yards cold-start fast route.

V106 preserves certified Router V105 behavior for every non-Rushing route while
allowing an already-active NFL -> Rushing Yards session to start without eagerly
importing the historical V77-V105 router spine. The final certified Rushing page
is V10, a performance-only wrapper over frozen Page Build V9.
"""
from __future__ import annotations

import importlib
import sys
from time import perf_counter
from typing import Any

import streamlit as st
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V106 • NFL RUSHING YARDS COLD-START FAST ROUTE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v105"
NFL_SPORT_LABEL = "NFL"
RUSHING_YARDS_MARKET = "Rushing Yards"
ACTIVE_PAGE = "nfl_rushing_yards_hub_v10"
ROUTE_QUERY_SPORT = "ks_nfl_sport"
ROUTE_QUERY_MARKET = "ks_nfl_market"

_ORIGINAL_SELECTBOX = root.st.selectbox
_ORIGINAL_RENDER_NFL = root._render_nfl
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
        if _query_value(ROUTE_QUERY_MARKET) != RUSHING_YARDS_MARKET:
            st.query_params[ROUTE_QUERY_MARKET] = RUSHING_YARDS_MARKET
    except Exception:
        pass


def _restore_fast_route_from_query() -> bool:
    current_sport = str(st.session_state.get("ks_sport_touch") or "").strip()
    current_market = str(st.session_state.get("ks_nfl_market_touch") or "").strip()
    if current_sport or current_market:
        return False
    if (
        _query_value(ROUTE_QUERY_SPORT) != NFL_SPORT_LABEL
        or _query_value(ROUTE_QUERY_MARKET) != RUSHING_YARDS_MARKET
    ):
        return False
    st.session_state["ks_sport_touch"] = NFL_SPORT_LABEL
    st.session_state["ks_nfl_market_touch"] = RUSHING_YARDS_MARKET
    return True


def _fast_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == NFL_SPORT_LABEL
        and str(st.session_state.get("ks_nfl_market_touch") or "") == RUSHING_YARDS_MARKET
    )


def _selectbox_v106(label: Any, options: Any, *args: Any, **kwargs: Any):
    selected = _ORIGINAL_SELECTBOX(label, options, *args, **kwargs)
    if label == "🏟️ Sport" and str(selected) != NFL_SPORT_LABEL:
        _clear_fast_route_query()
    elif label == "🎯 NFL Market":
        if str(selected) == RUSHING_YARDS_MARKET:
            _persist_fast_route_query()
        else:
            _clear_fast_route_query()
    return selected


def _render_nfl_v106(market: str) -> None:
    if market != RUSHING_YARDS_MARKET:
        prior = _load_prior()
        return prior._render_nfl_v105(market)

    _persist_fast_route_query()
    legacy_chain_skipped = FROZEN_ROUTER not in sys.modules
    page_import_started = perf_counter()
    mod = root._import(ACTIVE_PAGE)
    page_import_ms = (perf_counter() - page_import_started) * 1000.0

    try:
        st.session_state["nfl_rushing_yards_cold_start_v1_last"] = {
            "version": MODEL_VERSION,
            "first_bootstrap_import_ms": _FIRST_BOOTSTRAP_IMPORT_MS,
            "active_page_import_ms": page_import_ms,
            "legacy_router_chain_skipped": legacy_chain_skipped,
            "restored_from_query": (
                _query_value(ROUTE_QUERY_SPORT) == NFL_SPORT_LABEL
                and _query_value(ROUTE_QUERY_MARKET) == RUSHING_YARDS_MARKET
            ),
            "frozen_router": FROZEN_ROUTER,
            "active_page": ACTIVE_PAGE,
            "projection_weight": 0.0,
            "may_modify_projection": False,
        }
    except Exception:
        pass

    return mod.render_nfl_hub(market)


def _render_direct_rushing() -> None:
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    root.st.selectbox = _selectbox_v106
    root._render_nfl = _render_nfl_v106
    if "nfl_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("nfl_",)

    try:
        root.render_app()
    finally:
        root.st.selectbox = original_selectbox
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    if not _fast_route_active():
        _restore_fast_route_from_query()
    if _fast_route_active():
        return _render_direct_rushing()
    return _load_prior().render_app()


__all__ = [
    "ACTIVE_PAGE",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "NFL_SPORT_LABEL",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "RUSHING_YARDS_MARKET",
    "_clear_fast_route_query",
    "_fast_route_active",
    "_load_prior",
    "_persist_fast_route_query",
    "_query_value",
    "_render_direct_rushing",
    "_render_nfl_v106",
    "_restore_fast_route_from_query",
    "_selectbox_v106",
    "record_bootstrap_import_ms",
    "render_app",
]
