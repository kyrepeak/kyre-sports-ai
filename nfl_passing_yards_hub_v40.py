"""NFL Passing Yards V40 — Phoenix matchup-selector display hotfix.

Additive display-only wrapper over V39. V38 already converts the compact
matchup header to Phoenix local time; V40 applies the same verified timezone
conversion to the Streamlit "Verified matchup" selector display without
changing the underlying option value used by the frozen V8 lookup map.

Frozen:
- V39 presentation grades;
- V38 compact-header Phoenix conversion;
- V37 smart-slate behavior;
- all projection/probability/market/edge calculations;
- sportsbook projection influence = 0.0%;
- stake sizing OFF.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

import streamlit as st

import nfl_passing_yards_hub_v39 as prior
from nfl_passing_yards_phoenix_time_v1 import phoenix_kickoff

MODEL_VERSION = "NFL PASSING YARDS V40 • PHOENIX MATCHUP SELECTOR"
FROZEN_PRIOR = "nfl_passing_yards_hub_v39"
DISPLAY_ONLY = True
TIMEZONE_DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

V8_DATE_KEY = "nfl_passing_yards_v8_date"
V8_DATE_INPUT_KEY = "nfl_passing_yards_v8_date_input"


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


def _phoenix_matchup_option(option: Any, slate_date: Any) -> str:
    """Format one frozen V8 matchup option for display only."""
    text = str(option if option is not None else "")
    if " • " not in text:
        return text
    matchup_text, clock_et = text.rsplit(" • ", 1)
    labels = phoenix_kickoff(_coerce_date(slate_date), clock_et)
    if labels is None:
        return text
    return f"{matchup_text} • {labels['clock']}"


def render_nfl_passing_yards_hub() -> None:
    original_selectbox = st.selectbox

    def phoenix_selectbox(label: str, options: Any, *args: Any, **kwargs: Any):
        if label == "Verified matchup":
            previous_format: Callable[[Any], Any] | None = kwargs.get("format_func")
            slate_date = _selected_slate_date()

            def format_func(option: Any) -> str:
                base = previous_format(option) if callable(previous_format) else option
                return _phoenix_matchup_option(base, slate_date)

            kwargs["format_func"] = format_func
        return original_selectbox(label, options, *args, **kwargs)

    st.selectbox = phoenix_selectbox
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        st.selectbox = original_selectbox


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V40 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "TIMEZONE_DISPLAY_ONLY",
    "V8_DATE_INPUT_KEY",
    "V8_DATE_KEY",
    "_phoenix_matchup_option",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
