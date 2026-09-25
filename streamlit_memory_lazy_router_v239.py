"""Streamlit router V239 — Passing Yards shared-interpreter no-purge route.

Additive over frozen V238. Hosted public evidence proved that the exact NFL ->
Passing Yards selection reaches the V85 import graph, then can fail while the
deep Passing Yards module chain is loading. V225 already documents the shared
Streamlit interpreter hazard: V187 temporarily adds nfl_ to a global purge
prefix set, so one session can remove NFL modules while another session is
using/importing them.

V239 removes that hazard only for NFL -> Passing Yards:
- prime V225's certified per-session route token before any V85 import;
- render the existing V1 shell/selectors directly for the active Passing route;
- never mutate root._ROUTE_MODULE_PREFIXES;
- never replace root._render_nfl;
- import and render V85 only after the no-purge route is committed.

Every non-Passing route delegates unchanged to frozen V238. No model, data,
probability, market, sportsbook, widget-key, or Monster behavior changes.
"""
from __future__ import annotations

import importlib

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v185 as handoff
import streamlit_memory_lazy_router_v225 as route_guard
import streamlit_memory_lazy_router_v238 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V239 • PASSING YARDS SHARED-INTERPRETER NO-PURGE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v238"
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
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NO_GLOBAL_NFL_PURGE = True


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

    return bool(prior._passing_requested())


def _prepare_passing_route() -> str:
    # Consume only an already-requested NFL category jump; native selectbox
    # selection simply leaves this as a no-op.
    handoff._consume_any_nfl_category_without_rerun()

    # This certified V225 guard makes V1's route purge a no-op for the current
    # Passing Yards session before the deep V85 import graph is touched.
    return route_guard._prime_passing_route_token_for_session()


def _render_v239_marker() -> None:
    st.markdown(
        '<span data-passing-yards-router-owner="v239" '
        'data-passing-yards-global-nfl-purge="disabled" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def _render_passing_shell_no_purge(importer=importlib.import_module) -> None:
    """Render the existing root shell without any shared NFL purge mutation."""
    st.set_page_config(
        page_title="Kyre Sports AI",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="auto",
    )
    root._apply_shell_css()

    st.markdown(
        '<div class="ks-shell">'
        '<div class="ks-eyebrow">Sports projection intelligence</div>'
        '<div class="ks-title">🧠 KYRE SPORTS AI</div>'
        '<div class="ks-sub">Memory-safe lazy loading • one sport and one market stack at a time.</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    sport = st.selectbox(
        "🏟️ Sport",
        ["MLB", "WNBA", "NFL"],
        key=SPORT_KEY,
    )
    if sport != "NFL":
        return

    if str(st.session_state.get(NFL_MARKET_KEY) or "") not in root.NFL_MARKETS:
        st.session_state.pop(NFL_MARKET_KEY, None)

    market = st.selectbox(
        "🎯 NFL Market",
        root.NFL_MARKETS,
        key=NFL_MARKET_KEY,
    )
    if market != PASSING_MARKET:
        return

    token = root._route_token("NFL", PASSING_MARKET)
    removed = root._purge_route_modules_if_needed(token)
    if removed:
        raise RuntimeError(
            f"V239 Passing Yards no-purge invariant violated: removed={removed}"
        )

    st.markdown(
        f'<div class="ks-route">{root.h(MODEL_VERSION)} • active: NFL → '
        f'{root.h(PASSING_MARKET)}</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"🏈 NFL • lazy route: {PASSING_MARKET}")

    module = importer(PASSING_HUB)
    module.render_nfl_hub(PASSING_MARKET)

    st.caption("Model probabilities are estimates — not guarantees.")


def render_app() -> None:
    if not _passing_requested():
        return prior.render_app()

    _prepare_passing_route()
    _render_v239_marker()
    return _render_passing_shell_no_purge()


__all__ = [
    "FROZEN_ROUTER",
    "MARKET_JUMP_QUERY_KEY",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "NFL_MARKET_KEY",
    "NO_GLOBAL_NFL_PURGE",
    "PASSING_HUB",
    "PASSING_MARKET",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_JUMP_QUERY_KEY",
    "SPORT_KEY",
    "_passing_requested",
    "_prepare_passing_route",
    "_query_value",
    "_render_passing_shell_no_purge",
    "_render_v239_marker",
    "record_bootstrap_import_ms",
    "render_app",
]
