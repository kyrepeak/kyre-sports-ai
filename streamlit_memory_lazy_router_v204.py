"""KYRE Streamlit Router V204 — Passing Yards universal page shell Step 3.

Additive over frozen V203. Only active NFL Passing Yards advances from V52 to
presentation-only V53. It preserves V203's certified cold-query handoff before
route classification. Moneyline and every unrelated route delegate unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v203 as prior
import streamlit_memory_lazy_router_v185 as handoff

MODEL_VERSION = "KYRE STREAMLIT ROUTER V204 • PASSING YARDS PAGE SHELL STEP 3"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v203"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v53"
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
RUNTIME_MARKER = "PASSING_YARDS_V204_STEP3_SHELL_READY"

def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)

def _active_route() -> tuple[str, str]:
    return prior._active_route()

def _cold_passing_yards_query_requested() -> bool:
    sport = handoff._query_value(handoff.SPORT_JUMP_QUERY_KEY)
    market = handoff._query_value(handoff.MARKET_JUMP_QUERY_KEY)
    return (
        str(sport or "").strip().upper() == "NFL"
        and str(market or "").strip() == PASSING_MARKET
    )

def render_app() -> None:
    cold_query = _cold_passing_yards_query_requested()
    sport, market = _active_route()
    if not (cold_query or (sport == "NFL" and market == PASSING_MARKET)):
        return prior.render_app()

    st.markdown(
        '<span data-passing-yards-v204-runtime="step3" '
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
    "MAY_MODIFY_PROJECTION",
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
