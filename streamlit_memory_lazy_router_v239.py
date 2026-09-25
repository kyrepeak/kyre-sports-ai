"""Streamlit router V239 — Passing Yards shared-interpreter purge guard.

Additive over frozen V238. Hosted Streamlit sessions share one interpreter.
V187's certified direct-prop dispatcher temporarily adds nfl_ to the root
route-module purge prefixes; on a fresh Passing Yards session that can remove
shared NFL modules while the V85 graph is importing in another rerun/session.

V239 intercepts only NFL -> Passing Yards, primes V225's already-certified
Passing Yards route token before importing/rendering V85, and reuses frozen
V188's direct Passing Yards handoff. This makes V187's route purge a no-op for
this session while preserving the existing shell and model/data behavior.

Every non-Passing-Yards route delegates unchanged to V238. V238, V237, V236,
V225, V188, V187, V85, model/data/math owners, and Monster owners stay frozen.
"""
from __future__ import annotations

import importlib

import streamlit as st

import streamlit_memory_lazy_router_v185 as handoff
import streamlit_memory_lazy_router_v188 as passing_base
import streamlit_memory_lazy_router_v225 as route_guard
import streamlit_memory_lazy_router_v238 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V239 • PASSING YARDS SHARED-INTERPRETER PURGE GUARD"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v238"
FROZEN_ROUTE_GUARD = "streamlit_memory_lazy_router_v225"
FROZEN_DIRECT_PROP_ROUTER = "streamlit_memory_lazy_router_v188"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v85"
NFL_SPORT = "NFL"
SPORT_KEY = "ks_sport_touch"
NFL_MARKET_KEY = "ks_nfl_market_touch"
SPORT_JUMP_QUERY_KEY = "ks_jump_sport"
MARKET_JUMP_QUERY_KEY = "ks_jump_market"
PRESENTATION_ONLY = True
ROUTE_HANDOFF_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False
MAY_MODIFY_WIDGET_KEYS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
_IMPORT_CACHE: dict[str, bool] = {}


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _query_value(key: str) -> str:
    raw = st.query_params.get(key)
    if isinstance(raw, list):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _cold_passing_yards_query_requested() -> bool:
    return (
        _query_value(SPORT_JUMP_QUERY_KEY).upper() == NFL_SPORT
        and _query_value(MARKET_JUMP_QUERY_KEY) == PASSING_MARKET
    )


def _active_passing_yards_route() -> bool:
    sport = str(st.session_state.get(SPORT_KEY) or "").strip().upper()
    market = str(st.session_state.get(NFL_MARKET_KEY) or "").strip()
    return sport == NFL_SPORT and market == PASSING_MARKET


def _prime_cold_passing_state() -> None:
    handoff._apply_nfl_category_state(PASSING_MARKET)
    for key in (SPORT_JUMP_QUERY_KEY, MARKET_JUMP_QUERY_KEY):
        try:
            del st.query_params[key]
        except Exception:
            pass


def _passing_hub_importable(importer=importlib.import_module) -> bool:
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


def _prime_passing_route_token() -> str:
    return route_guard._prime_passing_route_token_for_session()


def _render_passing_yards_direct() -> None:
    st.markdown(
        '<span data-passing-yards-router-owner="v239" '
        'data-passing-yards-route-handoff="v225-guard-v188-v85" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )

    original = passing_base.PASSING_HUB
    passing_base.PASSING_HUB = PASSING_HUB
    try:
        return passing_base._render_passing_v188()
    finally:
        passing_base.PASSING_HUB = original


def render_app() -> None:
    cold = _cold_passing_yards_query_requested()
    active = _active_passing_yards_route()

    if not (cold or active):
        return prior.render_app()

    if cold:
        _prime_cold_passing_state()

    # Prime before the V85 import and before V188/V187 enter the root shell.
    # V225's certified session token makes the direct-prop route purge a no-op.
    _prime_passing_route_token()

    if not _passing_hub_importable():
        return prior.render_app()

    return _render_passing_yards_direct()


__all__ = [
    "FROZEN_DIRECT_PROP_ROUTER",
    "FROZEN_ROUTE_GUARD",
    "FROZEN_ROUTER",
    "MARKET_JUMP_QUERY_KEY",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "NFL_MARKET_KEY",
    "NFL_SPORT",
    "PASSING_HUB",
    "PASSING_MARKET",
    "PRESENTATION_ONLY",
    "ROUTE_HANDOFF_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_JUMP_QUERY_KEY",
    "SPORT_KEY",
    "STAKE_SIZING_ENABLED",
    "_active_passing_yards_route",
    "_cold_passing_yards_query_requested",
    "_passing_hub_importable",
    "_prime_cold_passing_state",
    "_prime_passing_route_token",
    "_render_passing_yards_direct",
    "record_bootstrap_import_ms",
    "render_app",
]
