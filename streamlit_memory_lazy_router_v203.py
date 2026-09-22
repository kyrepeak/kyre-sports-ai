"""KYRE Streamlit Router V203 — Passing Yards universal tokens Step 2.

Additive over frozen V202. Only active NFL Passing Yards advances from V51 to
presentation-only V52. NFL Moneyline and every unrelated route remain delegated
through V202 unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v202 as prior
import streamlit_memory_lazy_router_v185 as handoff

MODEL_VERSION = "KYRE STREAMLIT ROUTER V203 • PASSING YARDS UNIVERSAL TOKENS STEP 2"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v202"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v52"
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
RUNTIME_MARKER = "PASSING_YARDS_V203_STEP2_COLD_ENTRY_READY"

def _consume_passing_yards_query_entry() -> bool:
    """Prime only an explicit cold NFL -> Passing Yards query before classification."""
    sport = handoff._query_value(handoff.SPORT_JUMP_QUERY_KEY)
    market = handoff._query_value(handoff.MARKET_JUMP_QUERY_KEY)
    if (
        str(sport or "").strip().upper() == "NFL"
        and str(market or "").strip() == PASSING_MARKET
    ):
        return bool(handoff._consume_any_nfl_category_without_rerun())
    return False

def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)

def _active_route() -> tuple[str, str]:
    return prior._active_route()

def render_app() -> None:
    _consume_passing_yards_query_entry()
    sport, market = _active_route()
    if sport != "NFL" or market != PASSING_MARKET:
        return prior.render_app()

    st.markdown(
        '<span data-passing-yards-v203-runtime="step2" '
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
    "_consume_passing_yards_query_entry",
    "record_bootstrap_import_ms",
    "render_app",
]
