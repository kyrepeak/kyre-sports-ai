"""NFL Passing Yards V12 — live-route + empty-slate UX hotfix.

V11 / Steps 1–10 remain unchanged. This wrapper only improves the first-load
slate experience: when the default current ET calendar date is verified and has
no NFL games, it searches forward (bounded to seven days) and opens the first
verified NFL slate with games. A date the user manually chooses is never
silently replaced on later reruns.

No projection, probability, market, or sportsbook math is changed.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable

import streamlit as st

import nfl_hub_v29 as nfl
import nfl_passing_yards_hub_v11 as prior

MODEL_VERSION = "NFL PASSING YARDS V12 • LIVE ROUTE + AUTO VERIFIED SLATE HOTFIX"
MAX_FORWARD_DAYS = 7
AUTO_RESOLVED_KEY = "nfl_passing_yards_v12_auto_slate_resolved"
V8_DATE_KEY = "nfl_passing_yards_v8_date"
V8_DATE_INPUT_KEY = "nfl_passing_yards_v8_date_input"


def _coerce_date(value, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return fallback


def _verified_games_present(games) -> bool:
    return bool(games is not None and hasattr(games, "empty") and not games.empty)


def find_next_verified_slate(
    start_day: date,
    loader: Callable = nfl.load_nfl_slate,
    max_forward_days: int = MAX_FORWARD_DAYS,
) -> tuple[date, int | None, str]:
    """Return the first fully verified non-empty slate from start_day forward.

    The search fails closed. If schedule verification fails for any day before a
    non-empty slate is found, no automatic jump is made because we could no
    longer prove that a later result is truly the *next* verified slate.
    """
    start_day = _coerce_date(start_day, datetime.now(nfl.ET).date())
    for offset in range(max(0, int(max_forward_days)) + 1):
        candidate = start_day + timedelta(days=offset)
        games, diag = loader(candidate.isoformat())
        diag = diag if isinstance(diag, dict) else {}
        if not diag.get("request_ok"):
            return start_day, None, "verification_failed"
        if _verified_games_present(games):
            return candidate, offset, "verified"
    return start_day, None, "no_games_in_window"


def prepare_initial_verified_slate() -> str:
    """Seed the certified V8 date widget once, without overriding user choices."""
    if st.session_state.get(AUTO_RESOLVED_KEY):
        return ""

    today_et = datetime.now(nfl.ET).date()
    selected = st.session_state.get(V8_DATE_INPUT_KEY, st.session_state.get(V8_DATE_KEY, today_et))
    selected = _coerce_date(selected, today_et)

    # A non-today value already in session state is treated as an explicit user
    # choice and is preserved exactly.
    if selected != today_et:
        st.session_state[AUTO_RESOLVED_KEY] = True
        return ""

    resolved, offset, status = find_next_verified_slate(selected)
    st.session_state[AUTO_RESOLVED_KEY] = True

    if status == "verified" and offset is not None and offset > 0:
        # This runs before V8 creates the widget during this rerun, so both keys
        # can be safely seeded to the verified future slate.
        st.session_state[V8_DATE_KEY] = resolved
        st.session_state[V8_DATE_INPUT_KEY] = resolved
        return (
            f"📅 No NFL games are scheduled on {selected.isoformat()} ET. "
            f"Opened the next verified NFL slate: {resolved.isoformat()} ET."
        )

    # Keep the default date intact when today already has games, the provider
    # fails verification, or no game is found in the bounded search window.
    st.session_state.setdefault(V8_DATE_KEY, selected)
    return ""


def render_nfl_passing_yards_hub() -> None:
    notice = prepare_initial_verified_slate()
    if notice:
        st.info(notice)
    return prior.render_nfl_passing_yards_hub()


__all__ = [
    "AUTO_RESOLVED_KEY",
    "MAX_FORWARD_DAYS",
    "MODEL_VERSION",
    "V8_DATE_INPUT_KEY",
    "V8_DATE_KEY",
    "find_next_verified_slate",
    "prepare_initial_verified_slate",
    "render_nfl_passing_yards_hub",
]
