"""NBA Spread Step 2 — additive production-router activation.

This overlay sits above the current production owner and temporarily extends
only the shared sport selector / frozen NFL-fallback dispatch seam used by the
legacy root shell. Existing MLB, WNBA, NFL, College Football and existing NBA
Over/Under files remain delegated unchanged.
"""
from __future__ import annotations

import importlib
import sys
from typing import Any, Callable

import streamlit as st

import streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1 as prior
import streamlit_memory_lazy_router_v1 as root
from nba_spread_step2_activation_v1 import extend_sport_options, is_nba_spread_route

MODEL_VERSION = "KYRE STREAMLIT ROUTER • NBA SPREAD STEP2 SITE ACTIVATION V1"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1"
NBA_SPORT_LABEL = "NBA"
NBA_MARKETS = ("Spread",)
NBA_MARKET_LABEL = "🎯 NBA Market"
ACTIVE_PAGE = "nba_spread_page_v1"
PROVIDER_RESILIENCE_PAGE = "nba_spread_page_provider_resilience_step3_r1"
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_nba_market"
ROUTE_SESSION_MARKET = "ks_nba_market_touch"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_EXISTING_NBA_WORKSTREAMS = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _query_value(key: str) -> str:
    try:
        raw: Any = st.query_params.get(key)
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _persist_nba_route_query() -> None:
    try:
        st.query_params[ROUTE_QUERY_SPORT] = NBA_SPORT_LABEL
        st.query_params[ROUTE_QUERY_MARKET] = NBA_MARKETS[0]
    except Exception:
        pass


def _clear_nba_route_query() -> None:
    try:
        if _query_value(ROUTE_QUERY_SPORT) == NBA_SPORT_LABEL:
            del st.query_params[ROUTE_QUERY_SPORT]
        if ROUTE_QUERY_MARKET in st.query_params:
            del st.query_params[ROUTE_QUERY_MARKET]
    except Exception:
        pass


def _restore_nba_route_from_query() -> bool:
    if _query_value(ROUTE_QUERY_SPORT) != NBA_SPORT_LABEL:
        return False
    if _query_value(ROUTE_QUERY_MARKET) not in {"", NBA_MARKETS[0]}:
        return False
    changed = (
        str(st.session_state.get("ks_sport_touch") or "") != NBA_SPORT_LABEL
        or str(st.session_state.get(ROUTE_SESSION_MARKET) or "") != NBA_MARKETS[0]
    )
    st.session_state["ks_sport_touch"] = NBA_SPORT_LABEL
    st.session_state[ROUTE_SESSION_MARKET] = NBA_MARKETS[0]
    return changed


def _make_selectbox_bridge(delegate: Callable[..., Any]) -> Callable[..., Any]:
    if getattr(delegate, "_nba_spread_step2_bridge", False):
        return delegate

    def _bridge(label: Any, options: Any, *args: Any, **kwargs: Any):
        if label == "🏟️ Sport":
            selected = delegate(label, extend_sport_options(options), *args, **kwargs)
            if str(selected) == NBA_SPORT_LABEL:
                _persist_nba_route_query()
            else:
                _clear_nba_route_query()
            return selected

        if (
            label == "🎯 NFL Market"
            and str(st.session_state.get("ks_sport_touch") or "") == NBA_SPORT_LABEL
        ):
            if str(st.session_state.get(ROUTE_SESSION_MARKET) or "") not in NBA_MARKETS:
                st.session_state.pop(ROUTE_SESSION_MARKET, None)
            clean_kwargs = dict(kwargs)
            clean_kwargs.pop("key", None)
            clean_kwargs.pop("index", None)
            selected = delegate(
                NBA_MARKET_LABEL,
                list(NBA_MARKETS),
                *args,
                key=ROUTE_SESSION_MARKET,
                **clean_kwargs,
            )
            _persist_nba_route_query()
            return selected

        return delegate(label, options, *args, **kwargs)

    _bridge._nba_spread_step2_bridge = True  # type: ignore[attr-defined]
    _bridge._nba_spread_step2_delegate = delegate  # type: ignore[attr-defined]
    return _bridge


def _render_nba_spread(market: str) -> Any:
    if not is_nba_spread_route(st.session_state.get("ks_sport_touch"), market):
        raise RuntimeError("NBA_SPREAD_STEP2_ROUTE_IDENTITY_MISMATCH")
    _persist_nba_route_query()
    page = importlib.import_module(PROVIDER_RESILIENCE_PAGE)
    return page.render_nba_spread_page()


def _make_render_nfl_bridge(delegate: Callable[[str], Any]) -> Callable[[str], Any]:
    if getattr(delegate, "_nba_spread_step2_bridge", False):
        return delegate

    def _bridge(market: str):
        if str(st.session_state.get("ks_sport_touch") or "") == NBA_SPORT_LABEL:
            return _render_nba_spread(str(market or NBA_MARKETS[0]))
        return delegate(market)

    _bridge._nba_spread_step2_bridge = True  # type: ignore[attr-defined]
    _bridge._nba_spread_step2_delegate = delegate  # type: ignore[attr-defined]
    return _bridge


def _patch_loaded_router_seams() -> tuple[Callable[..., Any], Callable[[str], Any], tuple[str, ...]]:
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES
    root.st.selectbox = _make_selectbox_bridge(original_selectbox)
    root._render_nfl = _make_render_nfl_bridge(original_render_nfl)
    if "nba_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("nba_",)

    for name, module in list(sys.modules.items()):
        if not name.startswith("streamlit_memory_lazy_router") or module is None:
            continue
        selectbox = getattr(module, "_ORIGINAL_SELECTBOX", None)
        if callable(selectbox):
            setattr(module, "_ORIGINAL_SELECTBOX", _make_selectbox_bridge(selectbox))
        renderer = getattr(module, "_ORIGINAL_RENDER_NFL", None)
        if callable(renderer):
            setattr(module, "_ORIGINAL_RENDER_NFL", _make_render_nfl_bridge(renderer))
    return original_selectbox, original_render_nfl, original_prefixes


def _restore_loaded_router_seams(
    original_selectbox: Callable[..., Any],
    original_render_nfl: Callable[[str], Any],
    original_prefixes: tuple[str, ...],
) -> None:
    for name, module in list(sys.modules.items()):
        if not name.startswith("streamlit_memory_lazy_router") or module is None:
            continue
        for attr in ("_ORIGINAL_SELECTBOX", "_ORIGINAL_RENDER_NFL"):
            value = getattr(module, attr, None)
            if getattr(value, "_nba_spread_step2_bridge", False):
                setattr(module, attr, getattr(value, "_nba_spread_step2_delegate"))
    root.st.selectbox = original_selectbox
    root._render_nfl = original_render_nfl
    root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> Any:
    _restore_nba_route_from_query()
    original_selectbox, original_render_nfl, original_prefixes = _patch_loaded_router_seams()
    try:
        return prior.render_app()
    finally:
        _restore_loaded_router_seams(original_selectbox, original_render_nfl, original_prefixes)


__all__ = [
    "ACTIVE_PAGE",
    "PROVIDER_RESILIENCE_PAGE",
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_EXISTING_NBA_WORKSTREAMS",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NBA_MARKETS",
    "NBA_MARKET_LABEL",
    "NBA_SPORT_LABEL",
    "NETWORK_CALLS_ADDED",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
