"""Streamlit lazy router V223 — Passing Yards Matchup Intelligence Step 3.

Additive over frozen Router V222. Only active NFL Passing Yards advances from
frozen V71 to presentation-only V72 matchup intelligence. Every unrelated route
delegates unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v222 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V223 • PASSING YARDS MATCHUP INTELLIGENCE STEP 3"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v222"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v72"
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
RUNTIME_MARKER = "PASSING_YARDS_V223_MATCHUP_INTELLIGENCE_STEP3_READY"


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _active_route() -> tuple[str, str]:
    return prior._active_route()


def _cold_passing_yards_query_requested() -> bool:
    return prior._cold_passing_yards_query_requested()


def render_app() -> None:
    cold_query = _cold_passing_yards_query_requested()
    sport, market = _active_route()
    if not (cold_query or (sport == "NFL" and market == PASSING_MARKET)):
        return prior.render_app()

    st.markdown(
        '<span data-passing-yards-v223-router-runtime="matchup-intelligence-step3" '
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
    "record_bootstrap_import_ms",
    "render_app",
]
