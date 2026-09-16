"""NFL Passing Yards V37 — smart verified slate controller.

Additive UI/controller wrapper over frozen V36. Reuses the certified V12
verified-slate finder so an empty selected NFL date advances to the next
verified slate with games before V8 renders its date widget. Obsolete empty-day
info notices are suppressed; schedule-provider failures remain visible and
fail-closed.

Projection, probability, market/edge, API transport, exact ESPN identity,
sportsbook influence, and stake behavior remain unchanged.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v12 as auto_slate
import nfl_passing_yards_hub_v36 as prior
from nfl_passing_yards_slate_controller_v1 import (
    is_empty_slate_notice,
    resolve_next_verified_slate_date,
)

MODEL_VERSION = "NFL PASSING YARDS V37 • SMART NEXT VERIFIED SLATE"
FROZEN_PRIOR = "nfl_passing_yards_hub_v36"
FROZEN_AUTO_SLATE = "nfl_passing_yards_hub_v12"
SMART_NEXT_SLATE = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

V8_DATE_KEY = "nfl_passing_yards_v8_date"
V8_DATE_INPUT_KEY = "nfl_passing_yards_v8_date_input"
V8_MATCHUP_KEY = "nfl_passing_yards_v8_matchup"
MAX_LOOKAHEAD_DAYS = 7


def _coerce_date(value: Any, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return fallback


def _selected_date() -> date:
    today_et = datetime.now(auto_slate.nfl.ET).date()
    value = st.session_state.get(
        V8_DATE_INPUT_KEY,
        st.session_state.get(V8_DATE_KEY, today_et),
    )
    return _coerce_date(value, today_et)


def _prime_smart_slate() -> dict[str, Any]:
    selected = _selected_date()
    result = resolve_next_verified_slate_date(
        selected,
        auto_slate.find_next_verified_slate,
        max_lookahead_days=MAX_LOOKAHEAD_DAYS,
    )
    if result.get("state") == "FOUND" and result.get("advanced"):
        resolved = result["resolved_date"]
        st.session_state[V8_DATE_KEY] = resolved
        st.session_state[V8_DATE_INPUT_KEY] = resolved
        st.session_state.pop(V8_MATCHUP_KEY, None)
        # The frozen V12 one-shot flag must not prevent a future user-selected
        # empty date from being resolved by this newer controller.
        st.session_state[auto_slate.AUTO_RESOLVED_KEY] = True
    return result


def render_nfl_passing_yards_hub() -> None:
    _prime_smart_slate()
    original_info = st.info

    def filtered_info(body: Any, *args: Any, **kwargs: Any):
        if is_empty_slate_notice(body):
            return None
        return original_info(body, *args, **kwargs)

    st.info = filtered_info
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        st.info = original_info


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V37 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "FROZEN_AUTO_SLATE",
    "FROZEN_PRIOR",
    "MAX_LOOKAHEAD_DAYS",
    "MODEL_VERSION",
    "SMART_NEXT_SLATE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "V8_DATE_INPUT_KEY",
    "V8_DATE_KEY",
    "V8_MATCHUP_KEY",
    "_prime_smart_slate",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
