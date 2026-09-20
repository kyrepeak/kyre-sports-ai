"""KYRE Streamlit Router V183 — NFL Passing Yards safe entry prime.

Replaces the broken V182 delete-reset strategy. V182 removed widget-owned
Streamlit session-state keys before the legacy router/widget chain rebuilt them,
which can surface as a redacted runtime KeyError. V183 bypasses V182 and
delegates directly to frozen V181.

For the exact NFL -> Passing Yards dropdown jump, V183 safely primes the date
controller + date-input state to the current Eastern calendar date and clears
only the non-widget V12 one-shot auto-slate flag. The certified V37/V40
smart-slate chain remains responsible for advancing to the next verified slate.

No model, probability, market, grading, CFB, or other NFL-market logic changes.
"""
from __future__ import annotations

from datetime import datetime
from typing import MutableMapping
from zoneinfo import ZoneInfo

import streamlit as st

import streamlit_memory_lazy_router_v181 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V183 • NFL PASSING YARDS SAFE ENTRY PRIME"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v181"
REPLACED_BROKEN_ROUTER = "streamlit_memory_lazy_router_v182"
SPORT_JUMP_QUERY_KEY = "ks_jump_sport"
MARKET_JUMP_QUERY_KEY = "ks_jump_market"
NFL_CODE = "NFL"
PASSING_YARDS_MARKET = "Passing Yards"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

V8_DATE_KEY = "nfl_passing_yards_v8_date"
V8_DATE_INPUT_KEY = "nfl_passing_yards_v8_date_input"
V12_AUTO_RESOLVED_KEY = "nfl_passing_yards_v12_auto_slate_resolved"
ET = ZoneInfo("America/New_York")

PRODUCTION_HEARTBEAT = (
    f"{prior.PRODUCTION_HEARTBEAT} • "
    "NFL_PASSING_YARDS_SAFE_ENTRY_PRIME_V183_ACTIVE"
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


def _prime_passing_yards_entry_state(
    state: MutableMapping[str, object],
    *,
    today_et=None,
) -> object:
    resolved_today = today_et or datetime.now(ET).date()

    # Safe widget-state prime: do not delete Streamlit widget-owned keys.
    state[V8_DATE_KEY] = resolved_today
    state[V8_DATE_INPUT_KEY] = resolved_today

    # This is a controller flag, not a widget key; clearing it re-enables the
    # existing V12/V37 smart-slate resolution on this fresh dropdown entry.
    state.pop(V12_AUTO_RESOLVED_KEY, None)
    return resolved_today


def _prime_passing_yards_entry_if_requested() -> bool:
    code = _query_value(SPORT_JUMP_QUERY_KEY)
    market = _query_value(MARKET_JUMP_QUERY_KEY)

    if not _passing_yards_jump_requested(code, market):
        return False

    _prime_passing_yards_entry_state(st.session_state)
    return True


def render_app() -> None:
    _prime_passing_yards_entry_if_requested()
    return prior.render_app()


__all__ = [
    "ET",
    "FROZEN_ROUTER",
    "MARKET_JUMP_QUERY_KEY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NFL_CODE",
    "PASSING_YARDS_MARKET",
    "PRODUCTION_HEARTBEAT",
    "REPLACED_BROKEN_ROUTER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_JUMP_QUERY_KEY",
    "V12_AUTO_RESOLVED_KEY",
    "V8_DATE_INPUT_KEY",
    "V8_DATE_KEY",
    "_passing_yards_jump_requested",
    "_prime_passing_yards_entry_if_requested",
    "_prime_passing_yards_entry_state",
    "record_bootstrap_import_ms",
    "render_app",
]
