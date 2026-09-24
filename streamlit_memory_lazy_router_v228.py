"""Streamlit lazy router V228 — Passing Yards Performance Step 8.

Additive over frozen Router V227. Only active NFL Passing Yards advances to V77.
The Step 8 hub preflight result is memoized after the first active-route check,
removing repeated import-probe work on Streamlit reruns. Unrelated routes and
all frozen Step 7 routing behavior delegate unchanged.
"""
from __future__ import annotations

import importlib

import streamlit as st
import streamlit_memory_lazy_router_v227 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V228 • PASSING YARDS PERFORMANCE STEP 8"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v227"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v77"
FALLBACK_HUB = "nfl_passing_yards_hub_v76"
PERFORMANCE_VERSION = "v77"
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
RUNTIME_MARKER = "PASSING_YARDS_V228_PERFORMANCE_STEP8_READY"

_DEFAULT_IMPORT_CACHE: dict[str, bool] = {}


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _active_route() -> tuple[str, str]:
    return prior._active_route()


def _cold_passing_yards_query_requested() -> bool:
    return prior._cold_passing_yards_query_requested()


def _step8_hub_importable(importer=importlib.import_module) -> bool:
    if importer is importlib.import_module and PASSING_HUB in _DEFAULT_IMPORT_CACHE:
        return _DEFAULT_IMPORT_CACHE[PASSING_HUB]
    try:
        importer(PASSING_HUB)
        ok = True
    except Exception:
        ok = False
    if importer is importlib.import_module:
        _DEFAULT_IMPORT_CACHE[PASSING_HUB] = ok
    return ok


def render_app() -> None:
    cold_query = _cold_passing_yards_query_requested()
    sport, market = _active_route()
    if not (cold_query or (sport == "NFL" and market == PASSING_MARKET)):
        return prior.render_app()

    if not _step8_hub_importable():
        return prior.render_app()

    st.markdown(
        '<span data-passing-yards-v228-router-runtime="performance-step8" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )

    original = prior.PASSING_HUB
    prior.PASSING_HUB = PASSING_HUB
    try:
        # Frozen V227 still owns route-token protection and Step 7 fail-closed routing.
        return prior.render_app()
    finally:
        prior.PASSING_HUB = original


__all__ = [
    "FALLBACK_HUB",
    "FROZEN_ROUTER",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PASSING_HUB",
    "PASSING_MARKET",
    "PERFORMANCE_VERSION",
    "PRESENTATION_ONLY",
    "RUNTIME_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_route",
    "_cold_passing_yards_query_requested",
    "_step8_hub_importable",
    "record_bootstrap_import_ms",
    "render_app",
]
