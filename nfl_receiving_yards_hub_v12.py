"""NFL Receiving Yards V12 — Phoenix research-matchup display.

Additive display-only wrapper over frozen V11. It changes only the visible
Receiver research matchup selector label from Eastern to Phoenix time while
preserving the underlying ESPN event option/value and all frozen calculations.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

import streamlit as st

from nfl_hub_v1 import ET
import nfl_receiving_yards_hub_v11 as prior
from nfl_receiving_yards_phoenix_time_v1 import format_research_matchup_label

MODEL_VERSION = "NFL RECEIVING YARDS V12 • PHOENIX RESEARCH MATCHUP TIME"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v11"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
RESEARCH_MATCHUP_LABEL = "🎯 Receiver research matchup"
DATE_KEY = "nfl_receiving_yards_v1_date"
DATE_INPUT_KEY = "nfl_receiving_yards_v1_date_input"


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
    today_et = datetime.now(ET).date()
    value = st.session_state.get(
        DATE_INPUT_KEY,
        st.session_state.get(DATE_KEY, today_et),
    )
    return _coerce_date(value, today_et)


def render_nfl_receiving_yards_hub() -> None:
    original_selectbox = st.selectbox
    game_date = _selected_date()

    def phoenix_selectbox(label: Any, *args: Any, **kwargs: Any):
        if str(label or "").strip() != RESEARCH_MATCHUP_LABEL:
            return original_selectbox(label, *args, **kwargs)

        original_format: Callable[[Any], Any] | None = kwargs.get("format_func")

        def phoenix_format(value: Any) -> str:
            raw = original_format(value) if callable(original_format) else str(value)
            return format_research_matchup_label(raw, game_date)

        kwargs["format_func"] = phoenix_format
        return original_selectbox(label, *args, **kwargs)

    st.selectbox = phoenix_selectbox
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        st.selectbox = original_selectbox


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V12 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "DATE_INPUT_KEY",
    "DATE_KEY",
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "RESEARCH_MATCHUP_LABEL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
