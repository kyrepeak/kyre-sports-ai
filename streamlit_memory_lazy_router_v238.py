"""Streamlit lazy router V238 — Passing Yards direct handoff repair.

Additive over current V237. This router exists for one narrowly scoped public
runtime failure: NFL -> Passing Yards can fall through the frozen router chain
to V187, whose direct handler correctly rejects non-player-prop fallback state.

V238 intercepts only the certified Passing Yards route at the top of the stack,
primes the already-existing Passing Yards route token, and reuses frozen V188's
certified direct-prop handoff with presentation-only V85.

Every non-Passing-Yards route delegates byte-for-behavior to V237. V236,
V187, all model/data/math owners, and every Monster/sitewide owner remain
untouched.
"""
from __future__ import annotations

import importlib

import streamlit as st

import streamlit_memory_lazy_router_v185 as handoff
import streamlit_memory_lazy_router_v188 as passing_base
import streamlit_memory_lazy_router_v225 as route_guard
import streamlit_memory_lazy_router_v237 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V238 • PASSING YARDS DIRECT HANDOFF REPAIR"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v237"
FROZEN_MONSTER_ROUTER = "streamlit_memory_lazy_router_v236"
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
    # Reuse V185's already-certified same-run NFL category handoff, including
    # the Passing Yards fresh-date prime, instead of creating new route state.
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


def _render_passing_yards_direct() -> None:
    # V225's public-session route-token guard prevents V187's direct-prop
    # prefix purge from removing shared NFL modules during this same session.
    route_guard._prime_passing_route_token_for_session()

    st.markdown(
        '<span data-passing-yards-route-handoff-owner="v238" '
        'data-passing-yards-route-handoff="direct-v188-v85" '
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

    # Fail closed to the current frozen chain if the presentation-only cleanup
    # hub is unavailable; never synthesize data or silently change math.
    if not _passing_hub_importable():
        return prior.render_app()

    return _render_passing_yards_direct()


__all__ = [
    "FROZEN_DIRECT_PROP_ROUTER",
    "FROZEN_MONSTER_ROUTER",
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
    "_render_passing_yards_direct",
    "record_bootstrap_import_ms",
    "render_app",
]
