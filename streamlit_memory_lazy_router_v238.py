"""Streamlit router V238 — Passing Yards runtime cache-bust owner.

Additive over V237. A new module identity is intentionally used so hosted
Streamlit cannot satisfy the app entrypoint with an already-imported V237
module after a hot source update.

Only NFL -> Passing Yards is owned here. That route installs V85 ownership and
enters V187's certified direct root-shell dispatcher. Every other route
delegates unchanged to V237 (and therefore V236/Monster behavior is preserved).
"""
from __future__ import annotations

import importlib

import streamlit as st

import streamlit_memory_lazy_router_v187 as identity_router
import streamlit_memory_lazy_router_v235 as passing_router
import streamlit_memory_lazy_router_v237 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V238 • PASSING YARDS RUNTIME CACHE BUST"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v237"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v85"
SPORT_KEY = "ks_sport_touch"
NFL_MARKET_KEY = "ks_nfl_market_touch"
SPORT_JUMP_QUERY_KEY = "ks_jump_sport"
MARKET_JUMP_QUERY_KEY = "ks_jump_market"
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


def _query_value(key: str) -> str:
    raw = st.query_params.get(key)
    if isinstance(raw, list):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _passing_requested() -> bool:
    sport_state = str(st.session_state.get(SPORT_KEY) or "").strip()
    market_state = str(st.session_state.get(NFL_MARKET_KEY) or "").strip()
    if sport_state == "NFL" and market_state == PASSING_MARKET:
        return True

    if (
        _query_value(SPORT_JUMP_QUERY_KEY).upper() == "NFL"
        and _query_value(MARKET_JUMP_QUERY_KEY) == PASSING_MARKET
    ):
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


def _install_passing_owners() -> None:
    passing_router.PASSING_HUB = PASSING_HUB
    identity_router.PROP_HUBS[PASSING_MARKET] = PASSING_HUB


def _render_v238_marker() -> None:
    st.markdown(
        '<span data-passing-yards-router-owner="v238" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def render_app() -> None:
    if not _passing_requested():
        return prior.render_app()
    if not _cleanup_hub_importable():
        return prior.render_app()

    _render_v238_marker()
    _install_passing_owners()
    return identity_router._render_direct_prop()


__all__ = [
    "FROZEN_ROUTER",
    "MARKET_JUMP_QUERY_KEY",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "NFL_MARKET_KEY",
    "PASSING_HUB",
    "PASSING_MARKET",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_JUMP_QUERY_KEY",
    "SPORT_KEY",
    "_cleanup_hub_importable",
    "_install_passing_owners",
    "_passing_requested",
    "_query_value",
    "_render_v238_marker",
    "record_bootstrap_import_ms",
    "render_app",
]
