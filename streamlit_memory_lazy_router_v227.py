"""Streamlit lazy router V227 — Passing Yards UX / Presentation Step 7.

Additive over frozen Router V226. Only active NFL Passing Yards advances from
frozen V75 to V76. Every unrelated route delegates unchanged.
"""
from __future__ import annotations

import importlib

import streamlit as st
import streamlit_memory_lazy_router_v226 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V227 • PASSING YARDS UX PRESENTATION STEP 7"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v226"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v76"
FALLBACK_HUB = "nfl_passing_yards_hub_v75"
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
RUNTIME_MARKER = "PASSING_YARDS_V227_UX_PRESENTATION_STEP7_READY"


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _active_route() -> tuple[str, str]:
    return prior._active_route()


def _cold_passing_yards_query_requested() -> bool:
    return prior._cold_passing_yards_query_requested()


def _step7_hub_importable(importer=importlib.import_module) -> bool:
    try:
        importer(PASSING_HUB)
    except Exception:
        return False
    return True


def render_app() -> None:
    cold_query = _cold_passing_yards_query_requested()
    sport, market = _active_route()
    if not (cold_query or (sport == "NFL" and market == PASSING_MARKET)):
        return prior.render_app()

    # Preserve Step 5's frozen fresh-session purge guard before active routing.
    prior.prior._prime_passing_route_token_for_session()

    # A broken/missing new Step 7 presentation module must not take down
    # frozen Step 6.
    if not _step7_hub_importable():
        return prior.render_app()

    st.markdown(
        '<span data-passing-yards-v227-router-runtime="ux-presentation-step7" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )

    original = prior.PASSING_HUB
    prior.PASSING_HUB = PASSING_HUB
    try:
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
    "PRESENTATION_ONLY",
    "RUNTIME_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_route",
    "_cold_passing_yards_query_requested",
    "_step7_hub_importable",
    "record_bootstrap_import_ms",
    "render_app",
]
