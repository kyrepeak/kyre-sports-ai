"""Streamlit lazy router V229 — Passing Yards speed Step 2.

Only active NFL Passing Yards advances from frozen V77 to V78. All unrelated
routes delegate unchanged to frozen Router V228. If V78 cannot import, routing
fails closed to the frozen V228/V77 path.
"""
from __future__ import annotations

import importlib

import streamlit_memory_lazy_router_v228 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V229 • PASSING YARDS SPEED STEP 2"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v228"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v78"
FALLBACK_HUB = "nfl_passing_yards_hub_v77"
FIRST_PAINT_VERSION = "v78"
PRESENTATION_ONLY = True
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


def _speed_hub_importable(importer=importlib.import_module) -> bool:
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
    cold_query = _cold_passing_yards_query_requested()
    sport, market = _active_route()
    if not (cold_query or (sport == "NFL" and market == PASSING_MARKET)):
        return prior.render_app()

    if not _speed_hub_importable():
        return prior.render_app()

    original = prior.PASSING_HUB
    prior.PASSING_HUB = PASSING_HUB
    try:
        return prior.render_app()
    finally:
        prior.PASSING_HUB = original


__all__ = [
    "FALLBACK_HUB",
    "FIRST_PAINT_VERSION",
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
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_route",
    "_cold_passing_yards_query_requested",
    "_speed_hub_importable",
    "record_bootstrap_import_ms",
    "render_app",
]
