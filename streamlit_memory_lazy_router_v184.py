"""KYRE Streamlit Router V184 — NFL Passing Yards no-rerun fresh handoff.

Fixes the live stuck-slate symptom that remained after V183. V183 primed the
Passing Yards date before V180 consumed the dropdown query, but V180 then called
st.rerun(). On the second run the jump query was gone and the browser's prior
widget state could restore the stale 2026-09-19 slate.

V184 consumes only the exact NFL -> Passing Yards dropdown handoff itself:
- writes the existing sport/market session route state;
- primes both Passing Yards date keys to current Eastern date;
- clears the non-widget smart-slate one-shot flag;
- removes the jump query;
- delegates in the SAME run (no rerun), allowing the frozen V141/V40/V37 stack
  to render and smart-advance normally.

A versioned one-shot migration also repairs already-open stale Passing Yards
sessions after deployment. No model, projection, market, grading, CFB, or other
NFL-market logic changes.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import MutableMapping
from zoneinfo import ZoneInfo

import streamlit as st

import streamlit_memory_lazy_router_v183 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V184 • NFL PASSING YARDS NO-RERUN FRESH HANDOFF"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v183"

SPORT_JUMP_QUERY_KEY = "ks_jump_sport"
MARKET_JUMP_QUERY_KEY = "ks_jump_market"
NFL_CODE = "NFL"
NFL_SPORT_VALUE = "NFL"
PASSING_YARDS_MARKET = "Passing Yards"
NFL_MARKET_KEY = "ks_nfl_market_touch"
SPORT_KEY = "ks_sport_touch"

V8_DATE_KEY = "nfl_passing_yards_v8_date"
V8_DATE_INPUT_KEY = "nfl_passing_yards_v8_date_input"
V12_AUTO_RESOLVED_KEY = "nfl_passing_yards_v12_auto_slate_resolved"
MIGRATION_KEY = "nfl_passing_yards_v184_stale_slate_migrated"

ET = ZoneInfo("America/New_York")
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

PRODUCTION_HEARTBEAT = (
    f"{prior.PRODUCTION_HEARTBEAT} • "
    "NFL_PASSING_YARDS_NO_RERUN_FRESH_HANDOFF_V184_ACTIVE"
)


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _query_value(key: str) -> str:
    raw = st.query_params.get(key)
    if isinstance(raw, list):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _coerce_date(value, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return fallback


def _passing_yards_jump_requested(code: str, market: str) -> bool:
    return (
        str(code or "").strip().upper() == NFL_CODE
        and str(market or "").strip() == PASSING_YARDS_MARKET
    )


def _passing_yards_route_active(state: MutableMapping[str, object]) -> bool:
    return (
        str(state.get(SPORT_KEY) or "") == NFL_SPORT_VALUE
        and str(state.get(NFL_MARKET_KEY) or "") == PASSING_YARDS_MARKET
    )


def _prime_fresh_passing_yards_state(
    state: MutableMapping[str, object],
    *,
    today_et: date,
) -> None:
    state[SPORT_KEY] = NFL_SPORT_VALUE
    state[NFL_MARKET_KEY] = PASSING_YARDS_MARKET
    state[V8_DATE_KEY] = today_et
    state[V8_DATE_INPUT_KEY] = today_et
    state.pop(V12_AUTO_RESOLVED_KEY, None)


def _consume_passing_yards_jump_without_rerun(*, today_et: date | None = None) -> bool:
    code = _query_value(SPORT_JUMP_QUERY_KEY)
    market = _query_value(MARKET_JUMP_QUERY_KEY)

    if not _passing_yards_jump_requested(code, market):
        return False

    resolved_today = today_et or datetime.now(ET).date()
    _prime_fresh_passing_yards_state(st.session_state, today_et=resolved_today)
    st.session_state[MIGRATION_KEY] = True

    for key in (SPORT_JUMP_QUERY_KEY, MARKET_JUMP_QUERY_KEY):
        try:
            del st.query_params[key]
        except Exception:
            pass

    return True


def _migrate_already_stuck_session_once(*, today_et: date | None = None) -> bool:
    if not _passing_yards_route_active(st.session_state):
        return False

    if st.session_state.get(MIGRATION_KEY):
        return False

    resolved_today = today_et or datetime.now(ET).date()
    selected = _coerce_date(
        st.session_state.get(V8_DATE_INPUT_KEY, st.session_state.get(V8_DATE_KEY)),
        resolved_today,
    )

    st.session_state[MIGRATION_KEY] = True

    # Only repair an actually stale prior-day session; do not override a
    # same-day user selection or a future manual selection.
    if selected >= resolved_today:
        return False

    _prime_fresh_passing_yards_state(st.session_state, today_et=resolved_today)
    return True


def render_app() -> None:
    consumed = _consume_passing_yards_jump_without_rerun()
    if not consumed:
        _migrate_already_stuck_session_once()

    # The exact Passing Yards jump query has already been removed, so V180
    # cannot trigger its category st.rerun path. Existing session route state
    # carries the request through frozen V141 -> V40 in this same script run.
    return prior.render_app()


__all__ = [
    "ET",
    "FROZEN_ROUTER",
    "MARKET_JUMP_QUERY_KEY",
    "MAY_MODIFY_PROJECTION",
    "MIGRATION_KEY",
    "MODEL_VERSION",
    "NFL_CODE",
    "NFL_MARKET_KEY",
    "NFL_SPORT_VALUE",
    "PASSING_YARDS_MARKET",
    "PRODUCTION_HEARTBEAT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_JUMP_QUERY_KEY",
    "SPORT_KEY",
    "V12_AUTO_RESOLVED_KEY",
    "V8_DATE_INPUT_KEY",
    "V8_DATE_KEY",
    "_consume_passing_yards_jump_without_rerun",
    "_migrate_already_stuck_session_once",
    "_passing_yards_jump_requested",
    "_passing_yards_route_active",
    "_prime_fresh_passing_yards_state",
    "record_bootstrap_import_ms",
    "render_app",
]
