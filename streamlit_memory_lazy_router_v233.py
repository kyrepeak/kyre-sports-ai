"""Streamlit lazy router V233 — Passing Yards speed Step 6."""
from __future__ import annotations

import importlib

import streamlit_memory_lazy_router_v232 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V233 • PASSING YARDS SPEED STEP 6"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v232"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v82"
FALLBACK_HUB = "nfl_passing_yards_hub_v81"
CONCURRENCY_VERSION = "v82"
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_IMPORT_CACHE: dict[str, bool] = {}


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _active_route() -> tuple[str, str]:
    return prior._active_route()


def _cold_passing_yards_query_requested() -> bool:
    return prior._cold_passing_yards_query_requested()


def _speed6_hub_importable(importer=importlib.import_module) -> bool:
    if importer is importlib.import_module and PASSING_HUB in _IMPORT_CACHE:
        return _IMPORT_CACHE[PASSING_HUB]
    try:
        importer(PASSING_HUB)
        ok = True
    except Exception:
        ok = False
    if importer is importlib.import_module:
        _IMPORT_CACHE[PASSING_HUB] = ok
    return ok


def render_app() -> None:
    cold = _cold_passing_yards_query_requested()
    sport, market = _active_route()
    if not (cold or (sport == "NFL" and market == PASSING_MARKET)):
        return prior.render_app()
    if not _speed6_hub_importable():
        return prior.render_app()
    original = prior.PASSING_HUB
    prior.PASSING_HUB = PASSING_HUB
    try:
        return prior.render_app()
    finally:
        prior.PASSING_HUB = original


__all__ = [
    "CONCURRENCY_VERSION","FALLBACK_HUB","FROZEN_ROUTER",
    "MAY_MODIFY_CONTEXT_MATH","MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE","MAY_MODIFY_PROBABILITY","MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS","MODEL_VERSION","PASSING_HUB","PASSING_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE","_active_route",
    "_cold_passing_yards_query_requested","_speed6_hub_importable",
    "record_bootstrap_import_ms","render_app",
]
