"""KYRE Streamlit Router V205 — Passing Yards universal cards Step 4.

Additive over frozen V204. Only active NFL Passing Yards advances from V53 to
presentation-only V54. It preserves V204's read-only cold-query detection and
lets frozen V203 remain the single owner of the certified state-mutating handoff.
Moneyline and every unrelated route delegate unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v204 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V205 • PASSING YARDS UNIVERSAL CARDS STEP 4"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v204"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v54"
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
RUNTIME_MARKER = "PASSING_YARDS_V205_STEP4_CARDS_READY"

def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)

def _active_route() -> tuple[str, str]:
    return prior._active_route()

def render_app() -> None:
    cold_query = prior._cold_passing_yards_query_requested()
    sport, market = _active_route()
    if not (cold_query or (sport == "NFL" and market == PASSING_MARKET)):
        return prior.render_app()

    st.markdown(
        '<span data-passing-yards-v205-runtime="step4" '
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
    "record_bootstrap_import_ms",
    "render_app",
]
