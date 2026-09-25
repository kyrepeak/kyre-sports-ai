"""Streamlit lazy router V237 — Passing Yards visible leak cleanup.

Additive over frozen V236. Receptions and every non-Passing-Yards route still
delegate to V236 unchanged. Only NFL -> Passing Yards swaps V235's Passing Hub
from frozen V84 to presentation-only V85.
"""
from __future__ import annotations

import importlib

import streamlit_memory_lazy_router_v235 as passing_router
import streamlit_memory_lazy_router_v236 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V237 • PASSING YARDS V85 CLEANUP"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v236"
FROZEN_PASSING_ROUTER = "streamlit_memory_lazy_router_v235"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v85"
FALLBACK_HUB = "nfl_passing_yards_hub_v84"
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_IMPORT_CACHE: dict[str, bool] = {}


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _passing_requested() -> bool:
    if passing_router._cold_passing_yards_query_requested():
        return True
    sport, market = passing_router._active_route()
    return sport == "NFL" and market == PASSING_MARKET


def _cleanup_hub_importable(importer=importlib.import_module) -> bool:
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
    if not _passing_requested():
        return prior.render_app()
    if not _cleanup_hub_importable():
        return prior.render_app()

    original = passing_router.PASSING_HUB
    passing_router.PASSING_HUB = PASSING_HUB
    try:
        return prior.render_app()
    finally:
        passing_router.PASSING_HUB = original


__all__ = [
    "FALLBACK_HUB",
    "FROZEN_PASSING_ROUTER",
    "FROZEN_ROUTER",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PASSING_HUB",
    "PASSING_MARKET",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_cleanup_hub_importable",
    "_passing_requested",
    "record_bootstrap_import_ms",
    "render_app",
]
