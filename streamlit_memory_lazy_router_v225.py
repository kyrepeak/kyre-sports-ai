"""Streamlit lazy router V225 — Passing Yards Availability + Game-Day Step 5.

Additive over frozen Router V224. Only active NFL Passing Yards advances from
frozen V73 to V74 Step 5. Every unrelated route delegates unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v224 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V225 • PASSING YARDS AVAILABILITY GAME-DAY STEP 5"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v224"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v74"
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
RUNTIME_MARKER = "PASSING_YARDS_V225_AVAILABILITY_GAME_DAY_STEP5_READY"
PUBLIC_SESSION_PURGE_GUARD = "passing-yards-session-route-token-v1"
SESSION_ROUTE_TOKEN_KEY = root._ROUTE_TOKEN_KEY
PASSING_ROUTE_TOKEN = root._route_token("NFL", PASSING_MARKET)


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _active_route() -> tuple[str, str]:
    return prior._active_route()


def _cold_passing_yards_query_requested() -> bool:
    return prior._cold_passing_yards_query_requested()


def _prime_passing_route_token_for_session(state=None) -> str:
    """Prevent V187's fresh-session route cleanup from purging shared NFL modules.

    Streamlit sessions share one interpreter. The frozen direct-prop route temporarily
    adds ``nfl_`` to the global purge prefixes; on a fresh Passing Yards session that
    can remove modules while another public session is still using/importing them.
    Priming only this session's already-selected route token makes the frozen purge a
    no-op for direct Passing Yards entry without changing any model or data behavior.
    """
    target = st.session_state if state is None else state
    target[SESSION_ROUTE_TOKEN_KEY] = PASSING_ROUTE_TOKEN
    return PASSING_ROUTE_TOKEN


def render_app() -> None:
    cold_query = _cold_passing_yards_query_requested()
    sport, market = _active_route()
    if not (cold_query or (sport == "NFL" and market == PASSING_MARKET)):
        return prior.render_app()

    _prime_passing_route_token_for_session()

    st.markdown(
        '<span data-passing-yards-v225-router-runtime="availability-game-day-step5" '
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
    "PASSING_ROUTE_TOKEN",
    "PUBLIC_SESSION_PURGE_GUARD",
    "SESSION_ROUTE_TOKEN_KEY",
    "PRESENTATION_ONLY",
    "RUNTIME_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_route",
    "_cold_passing_yards_query_requested",
    "_prime_passing_route_token_for_session",
    "record_bootstrap_import_ms",
    "render_app",
]
