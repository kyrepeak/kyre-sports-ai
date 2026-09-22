"""KYRE Streamlit Router V191 — remaining-pages universal compatibility.

Additive over frozen V190. Already-certified presentations remain untouched:
NFL Passing Yards, NFL Moneyline, and CFB Game Total. Every other active route
renders inside one scoped Streamlit container with the universal compatibility
skin. Route/data/model owners remain V190 and its frozen delegates.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v190 as prior
from kyre_remaining_pages_theme_v1 import (
    REMAINING_PAGES_CONTAINER_KEY,
    build_remaining_pages_theme_css,
    should_theme_route,
)

MODEL_VERSION = "KYRE STREAMLIT ROUTER V191 • REMAINING PAGES UNIVERSAL THEME"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v190"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
PRESENTATION_ONLY = True

def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)

def _active_route() -> tuple[str, str]:
    sport = str(st.session_state.get("ks_sport_touch") or "").strip().upper()
    if sport == "NFL":
        market = str(st.session_state.get("ks_nfl_market_touch") or "").strip()
    elif sport == "CFB":
        market = str(st.session_state.get("ks_cfb_market_touch") or "").strip()
    elif sport == "MLB":
        market = str(st.session_state.get("ks_mlb_market_touch") or "").strip()
    elif sport == "WNBA":
        market = str(st.session_state.get("ks_wnba_market_touch") or "").strip()
    else:
        market = ""
    return sport, market

def render_app() -> None:
    sport, market = _active_route()
    if not should_theme_route(sport, market):
        return prior.render_app()

    st.markdown(build_remaining_pages_theme_css(), unsafe_allow_html=True)
    themed = st.container(key=REMAINING_PAGES_CONTAINER_KEY)
    with themed:
        return prior.render_app()

__all__ = [
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_route",
    "record_bootstrap_import_ms",
    "render_app",
]
