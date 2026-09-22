"""KYRE Streamlit Router V182 — NFL Passing Yards clean-entry slate reset.

Additive over frozen Router V181. When the sport-dropdown jump is exactly
NFL -> Passing Yards, clear only Passing Yards' stale date/matchup one-shot UI
state before V181/V180 consume the query. This lets the already-certified
V37/V40 smart-slate chain start from the current ET date and advance to the
next verified slate when necessary.

No model, probability, market, grading, CFB, or other NFL-market logic changes.
"""
from __future__ import annotations

from typing import MutableMapping

import streamlit as st

import streamlit_memory_lazy_router_v181 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V182 • NFL PASSING YARDS CLEAN ENTRY SLATE RESET"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v181"
SPORT_JUMP_QUERY_KEY = "ks_jump_sport"
MARKET_JUMP_QUERY_KEY = "ks_jump_market"
NFL_CODE = "NFL"
PASSING_YARDS_MARKET = "Passing Yards"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

PASSING_YARDS_ENTRY_STATE_KEYS = (
    "nfl_passing_yards_v8_date",
    "nfl_passing_yards_v8_date_input",
    "nfl_passing_yards_v8_matchup",
    "nfl_passing_yards_v12_auto_slate_resolved",
)

PRODUCTION_HEARTBEAT = (
    f"{prior.PRODUCTION_HEARTBEAT} • "
    "NFL_PASSING_YARDS_CLEAN_ENTRY_SLATE_RESET_V182_ACTIVE"
)


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _query_value(key: str) -> str:
    raw = st.query_params.get(key)
    if isinstance(raw, list):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _passing_yards_jump_requested(code: str, market: str) -> bool:
    return (
        str(code or "").strip().upper() == NFL_CODE
        and str(market or "").strip() == PASSING_YARDS_MARKET
    )


def _clear_passing_yards_entry_state(state: MutableMapping[str, object]) -> None:
    for key in PASSING_YARDS_ENTRY_STATE_KEYS:
        state.pop(key, None)


def _reset_passing_yards_entry_state_if_requested() -> bool:
    code = _query_value(SPORT_JUMP_QUERY_KEY)
    market = _query_value(MARKET_JUMP_QUERY_KEY)

    if not _passing_yards_jump_requested(code, market):
        return False

    _clear_passing_yards_entry_state(st.session_state)
    return True


def render_app() -> None:
    _reset_passing_yards_entry_state_if_requested()
    return prior.render_app()


__all__ = [
    "FROZEN_ROUTER",
    "MARKET_JUMP_QUERY_KEY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NFL_CODE",
    "PASSING_YARDS_ENTRY_STATE_KEYS",
    "PASSING_YARDS_MARKET",
    "PRODUCTION_HEARTBEAT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_JUMP_QUERY_KEY",
    "_clear_passing_yards_entry_state",
    "_passing_yards_jump_requested",
    "_reset_passing_yards_entry_state_if_requested",
    "record_bootstrap_import_ms",
    "render_app",
]
