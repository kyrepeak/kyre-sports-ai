"""Streamlit lazy router V236 — NFL Receptions route handoff repair.

Additive over frozen V235. Intercepts only NFL -> Receptions so the reserved
fail-closed Receptions surface reliably renders after either a real UI
selection or the existing sitewide category-jump query.

All other routes delegate byte-for-behavior to V235.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v235 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V236 • NFL RECEPTIONS ROUTE HANDOFF"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v235"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
PRESENTATION_ONLY = True

NFL_SPORT = "NFL"
RECEPTIONS_MARKET = "Receptions"
SPORT_KEY = "ks_sport_touch"
NFL_MARKET_KEY = "ks_nfl_market_touch"
SPORT_JUMP_QUERY_KEY = "ks_jump_sport"
MARKET_JUMP_QUERY_KEY = "ks_jump_market"
RECEPTIONS_ROUTE_MARKER = "NFL_RECEPTIONS_FAIL_CLOSED_V236_ACTIVE"


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _query_value(key: str) -> str:
    raw = st.query_params.get(key)
    if isinstance(raw, list):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _cold_receptions_query_requested() -> bool:
    return (
        _query_value(SPORT_JUMP_QUERY_KEY).upper() == NFL_SPORT
        and _query_value(MARKET_JUMP_QUERY_KEY) == RECEPTIONS_MARKET
    )


def _prime_receptions_query_state() -> None:
    st.session_state[SPORT_KEY] = NFL_SPORT
    st.session_state[NFL_MARKET_KEY] = RECEPTIONS_MARKET
    for key in (SPORT_JUMP_QUERY_KEY, MARKET_JUMP_QUERY_KEY):
        try:
            del st.query_params[key]
        except Exception:
            pass


def _active_receptions_route() -> bool:
    sport, market = prior._active_route()
    return sport == NFL_SPORT and market == RECEPTIONS_MARKET


def _render_receptions_surface() -> None:
    st.markdown(
        (
            '<div data-nfl-receptions-route="v236" '
            f'data-route-marker="{RECEPTIONS_ROUTE_MARKER}"></div>'
        ),
        unsafe_allow_html=True,
    )
    st.markdown("### 🎯 NFL Receptions")
    st.warning(
        "Receptions is fail-closed at the Step 7 app identity gate. "
        "No player identity is rendered until an independent exact-ID Receptions "
        "surface is certified against the shared current receiver pool."
    )
    st.caption(
        "Route health: active • identity gate: fail-closed • "
        "sportsbook projection influence: 0.0%"
    )


def render_app() -> None:
    if _cold_receptions_query_requested():
        _prime_receptions_query_state()
        return _render_receptions_surface()

    if _active_receptions_route():
        return _render_receptions_surface()

    return prior.render_app()


__all__ = [
    "FROZEN_ROUTER",
    "MARKET_JUMP_QUERY_KEY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NFL_MARKET_KEY",
    "NFL_SPORT",
    "PRESENTATION_ONLY",
    "RECEPTIONS_MARKET",
    "RECEPTIONS_ROUTE_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_JUMP_QUERY_KEY",
    "SPORT_KEY",
    "_active_receptions_route",
    "_cold_receptions_query_requested",
    "_prime_receptions_query_state",
    "_render_receptions_surface",
    "record_bootstrap_import_ms",
    "render_app",
]
