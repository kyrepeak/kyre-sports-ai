"""Streamlit Router V240 — NFL Prop Analytics Step 1 route ownership.

Additive over frozen V239. It adds one sibling NFL market, Prop Analytics, to
the shared NFL selector at render time and owns only that route. Every existing
market delegates unchanged to frozen V239.

The frozen root router and frozen Passing Yards V239/V85 owners are not edited.
"""
from __future__ import annotations

import importlib

import streamlit as st

import streamlit_memory_lazy_router_v239 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V240 • NFL PROP ANALYTICS STEP 1"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v239"
PROP_ANALYTICS_MARKET = "Prop Analytics"
PROP_ANALYTICS_HUB = "nfl_prop_analytics_hub_v1"
NFL_SPORT = "NFL"
SPORT_KEY = "ks_sport_touch"
NFL_MARKET_KEY = "ks_nfl_market_touch"
SPORT_JUMP_QUERY_KEY = "ks_jump_sport"
MARKET_JUMP_QUERY_KEY = "ks_jump_market"
ROUTE_OWNERSHIP_ONLY = True
MAY_MODIFY_PASSING_YARDS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_IMPORT_CACHE: dict[str, bool] = {}


def _root_router():
    """Load the shared root only after frozen V239 has fully initialized."""
    return importlib.import_module("streamlit_memory_lazy_router_v1")


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _query_value(key: str) -> str:
    raw = st.query_params.get(key)
    if isinstance(raw, list):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _prop_market_options() -> list[str]:
    root = _root_router()
    options = list(root.NFL_MARKETS)
    if PROP_ANALYTICS_MARKET not in options:
        options.append(PROP_ANALYTICS_MARKET)
    return options


def _install_prop_market_option() -> None:
    """Register Prop Analytics as a stable additive NFL selector option."""
    root = _root_router()
    if PROP_ANALYTICS_MARKET not in root.NFL_MARKETS:
        root.NFL_MARKETS = _prop_market_options()


def _with_prop_analytics_selectbox(callback):
    """Append Prop Analytics only to the rendered NFL market selector."""
    original_selectbox = st.selectbox

    def selectbox_with_prop_analytics(label, options, *args, **kwargs):
        resolved = list(options)
        if str(label or "").strip() == "🎯 NFL Market":
            if PROP_ANALYTICS_MARKET not in resolved:
                resolved.append(PROP_ANALYTICS_MARKET)
        return original_selectbox(label, resolved, *args, **kwargs)

    st.selectbox = selectbox_with_prop_analytics
    try:
        return callback()
    finally:
        st.selectbox = original_selectbox


def _cold_prop_analytics_query_requested() -> bool:
    return (
        _query_value(SPORT_JUMP_QUERY_KEY).upper() == NFL_SPORT
        and _query_value(MARKET_JUMP_QUERY_KEY) == PROP_ANALYTICS_MARKET
    )


def _active_prop_analytics_route() -> bool:
    sport = str(st.session_state.get(SPORT_KEY) or "").strip().upper()
    market = str(st.session_state.get(NFL_MARKET_KEY) or "").strip()
    return sport == NFL_SPORT and market == PROP_ANALYTICS_MARKET


def _prime_cold_prop_analytics_state() -> None:
    st.session_state[SPORT_KEY] = NFL_SPORT
    st.session_state[NFL_MARKET_KEY] = PROP_ANALYTICS_MARKET
    for key in (SPORT_JUMP_QUERY_KEY, MARKET_JUMP_QUERY_KEY):
        try:
            del st.query_params[key]
        except Exception:
            pass


def _prop_hub_importable(importer=importlib.import_module) -> bool:
    # Cache only a confirmed success. Streamlit Cloud can hot-reload the new
    # router before a sibling module is visible on disk; caching that transient
    # miss would poison the process for the rest of its lifetime.
    if importer is importlib.import_module and _IMPORT_CACHE.get(PROP_ANALYTICS_HUB) is True:
        return True
    try:
        if importer is importlib.import_module:
            importlib.invalidate_caches()
        importer(PROP_ANALYTICS_HUB)
    except Exception:
        return False
    if importer is importlib.import_module:
        _IMPORT_CACHE[PROP_ANALYTICS_HUB] = True
    return True


def _render_nfl_v240(market: str) -> None:
    normalized = str(market or "").strip()
    if normalized != PROP_ANALYTICS_MARKET:
        raise RuntimeError("Router V240 direct handler is Prop Analytics only.")
    module = importlib.import_module(PROP_ANALYTICS_HUB)
    return module.render_nfl_hub(normalized)


def _render_direct_prop_analytics() -> None:
    root = _root_router()
    _install_prop_market_option()
    original_render_nfl = root._render_nfl
    root._render_nfl = _render_nfl_v240
    try:
        return _with_prop_analytics_selectbox(root.render_app)
    finally:
        root._render_nfl = original_render_nfl


def _delegate_with_prop_option() -> None:
    # Register the new sibling route and extend only the rendered NFL market
    # selector; every existing route still delegates to frozen V239 unchanged.
    _install_prop_market_option()
    return _with_prop_analytics_selectbox(prior.render_app)


def render_app() -> None:
    cold = _cold_prop_analytics_query_requested()
    if cold:
        _prime_cold_prop_analytics_state()

    if cold or _active_prop_analytics_route():
        if not _prop_hub_importable():
            return _delegate_with_prop_option()
        return _render_direct_prop_analytics()

    return _delegate_with_prop_option()


__all__ = [
    "FROZEN_ROUTER",
    "MARKET_JUMP_QUERY_KEY",
    "MAY_MODIFY_PASSING_YARDS",
    "MODEL_VERSION",
    "NFL_MARKET_KEY",
    "NFL_SPORT",
    "PROP_ANALYTICS_HUB",
    "PROP_ANALYTICS_MARKET",
    "ROUTE_OWNERSHIP_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_JUMP_QUERY_KEY",
    "SPORT_KEY",
    "_active_prop_analytics_route",
    "_cold_prop_analytics_query_requested",
    "_delegate_with_prop_option",
    "_install_prop_market_option",
    "_prime_cold_prop_analytics_state",
    "_prop_hub_importable",
    "_prop_market_options",
    "_query_value",
    "_root_router",
    "_with_prop_analytics_selectbox",
    "_render_direct_prop_analytics",
    "_render_nfl_v240",
    "record_bootstrap_import_ms",
    "render_app",
]
