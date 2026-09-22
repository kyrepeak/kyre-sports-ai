"""KYRE Streamlit Router V185 — all NFL dropdowns same-run handoff.

Live evidence showed multiple NFL pages failing after category selection.
The shared cause is V180's category handoff: it writes sport/market state and
then calls st.rerun(), allowing stale widget/session state to reassert itself
on the second run.

V185 consumes every valid NFL dropdown category before V180:
- validates against the frozen NFL_MARKETS contract;
- writes the existing ks_sport_touch + ks_nfl_market_touch state;
- removes only the jump-query keys;
- delegates in the SAME run, with no rerun.

Passing Yards preserves V184's fresh-date prime. All other NFL market/model
code remains frozen and continues through the existing router stack.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

import streamlit_memory_lazy_router_v1 as base
import streamlit_memory_lazy_router_v184 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V185 • ALL NFL SAME-RUN CATEGORY HANDOFF"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v184"

SPORT_JUMP_QUERY_KEY = "ks_jump_sport"
MARKET_JUMP_QUERY_KEY = "ks_jump_market"
SPORT_KEY = "ks_sport_touch"
NFL_MARKET_KEY = "ks_nfl_market_touch"
NFL_CODE = "NFL"
NFL_SPORT_VALUE = "NFL"
PASSING_YARDS_MARKET = "Passing Yards"
NFL_MARKETS = tuple(base.NFL_MARKETS)
ET = ZoneInfo("America/New_York")

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

PRODUCTION_HEARTBEAT = (
    f"{prior.PRODUCTION_HEARTBEAT} • "
    "NFL_ALL_MARKETS_SAME_RUN_HANDOFF_V185_ACTIVE"
)


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _query_value(key: str) -> str:
    raw = st.query_params.get(key)
    if isinstance(raw, list):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _valid_nfl_category_jump(code: str, market: str) -> bool:
    return (
        str(code or "").strip().upper() == NFL_CODE
        and str(market or "").strip() in NFL_MARKETS
    )


def _apply_nfl_category_state(market: str) -> None:
    market = str(market or "").strip()
    st.session_state[SPORT_KEY] = NFL_SPORT_VALUE
    st.session_state[NFL_MARKET_KEY] = market

    # Preserve the already-certified Passing Yards fresh-entry behavior.
    if market == PASSING_YARDS_MARKET:
        prior._prime_fresh_passing_yards_state(
            st.session_state,
            today_et=datetime.now(ET).date(),
        )
        st.session_state[prior.MIGRATION_KEY] = True


def _consume_any_nfl_category_without_rerun() -> bool:
    code = _query_value(SPORT_JUMP_QUERY_KEY)
    market = _query_value(MARKET_JUMP_QUERY_KEY)

    if not _valid_nfl_category_jump(code, market):
        return False

    _apply_nfl_category_state(market)

    for key in (SPORT_JUMP_QUERY_KEY, MARKET_JUMP_QUERY_KEY):
        try:
            del st.query_params[key]
        except Exception:
            pass

    return True


def render_app() -> None:
    _consume_any_nfl_category_without_rerun()
    return prior.render_app()


__all__ = [
    "ET",
    "FROZEN_ROUTER",
    "MARKET_JUMP_QUERY_KEY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NFL_CODE",
    "NFL_MARKETS",
    "NFL_MARKET_KEY",
    "NFL_SPORT_VALUE",
    "PASSING_YARDS_MARKET",
    "PRODUCTION_HEARTBEAT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_JUMP_QUERY_KEY",
    "SPORT_KEY",
    "_apply_nfl_category_state",
    "_consume_any_nfl_category_without_rerun",
    "_valid_nfl_category_jump",
    "record_bootstrap_import_ms",
    "render_app",
]
