"""NFL Passing Yards V38 — Phoenix, Arizona kickoff-time display.

Additive display-only wrapper over V37. It changes only the visible verified
matchup kickoff from the frozen Eastern slate clock to Phoenix local time using
IANA zoneinfo. V37 smart-slate behavior and all frozen analytical/model/market
contracts remain unchanged.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v36 as header
import nfl_passing_yards_hub_v37 as prior
from nfl_passing_yards_phoenix_time_v1 import PHOENIX_TZ_NAME, phoenix_kickoff

MODEL_VERSION = "NFL PASSING YARDS V38 • PHOENIX GAME TIMES"
FROZEN_PRIOR = "nfl_passing_yards_hub_v37"
FROZEN_HEADER = "nfl_passing_yards_hub_v36"
DISPLAY_ONLY = True
TIMEZONE_DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

V8_DATE_KEY = "nfl_passing_yards_v8_date"
V8_DATE_INPUT_KEY = "nfl_passing_yards_v8_date_input"
_ORIGINAL_MATCHUP_HEADER_V36 = header._matchup_header


def _coerce_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value if value is not None else "").strip()
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except Exception:
        return ""


def _selected_slate_date() -> str:
    value = st.session_state.get(
        V8_DATE_INPUT_KEY,
        st.session_state.get(V8_DATE_KEY, ""),
    )
    return _coerce_date(value)


def _phoenix_matchup_header(matchup: dict[str, str]) -> str:
    display_matchup = dict(matchup or {})
    labels = phoenix_kickoff(
        _selected_slate_date(),
        display_matchup.get("tip_et"),
    )
    if labels is not None:
        display_matchup["tip_et"] = labels["clock"]
    return _ORIGINAL_MATCHUP_HEADER_V36(display_matchup)


def render_nfl_passing_yards_hub() -> None:
    original_header = header._matchup_header
    header._matchup_header = _phoenix_matchup_header
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        header._matchup_header = original_header


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V38 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_HEADER",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "PHOENIX_TZ_NAME",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "TIMEZONE_DISPLAY_ONLY",
    "V8_DATE_INPUT_KEY",
    "V8_DATE_KEY",
    "_phoenix_matchup_header",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
