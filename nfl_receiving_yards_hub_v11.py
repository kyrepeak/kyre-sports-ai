"""NFL Receiving Yards V11 — smart next verified slate.

Additive UI/controller wrapper over frozen V10. It reuses the already-certified
verified-slate finder so an empty selected NFL date advances to the next verified
slate before the frozen Receiving page renders. Provider failures remain visible
and fail closed.

Projection math, market semantics, exact ESPN identity, matchup tiers,
probability/EV/staking behavior, and sportsbook influence remain unchanged.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v10 as prior
from nfl_hub_v1 import ET
from nfl_passing_yards_hub_v12 import find_next_verified_slate
from nfl_receiving_yards_slate_controller_v1 import (
    is_empty_slate_notice,
    resolve_next_verified_slate_date,
)

MODEL_VERSION = "NFL RECEIVING YARDS V11 • SMART NEXT VERIFIED SLATE"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v10"
SMART_NEXT_SLATE = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

DATE_KEY = "nfl_receiving_yards_v1_date"
DATE_INPUT_KEY = "nfl_receiving_yards_v1_date_input"
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
    today_et = datetime.now(ET).date()
    value = st.session_state.get(
        DATE_INPUT_KEY,
        st.session_state.get(DATE_KEY, today_et),
    )
    return _coerce_date(value, today_et)


def _prime_smart_slate() -> dict[str, Any]:
    selected = _selected_date()
    result = resolve_next_verified_slate_date(
        selected,
        find_next_verified_slate,
        max_lookahead_days=MAX_LOOKAHEAD_DAYS,
    )
    if result.get("state") == "FOUND" and result.get("advanced"):
        resolved = result["resolved_date"]
        st.session_state[DATE_KEY] = resolved
        st.session_state[DATE_INPUT_KEY] = resolved
    return result


def render_nfl_receiving_yards_hub() -> None:
    _prime_smart_slate()
    original_info = st.info

    def filtered_info(body: Any, *args: Any, **kwargs: Any):
        if is_empty_slate_notice(body):
            return None
        return original_info(body, *args, **kwargs)

    st.info = filtered_info
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        st.info = original_info


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V11 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "DATE_INPUT_KEY",
    "DATE_KEY",
    "FROZEN_PRIOR",
    "MAX_LOOKAHEAD_DAYS",
    "MODEL_VERSION",
    "SMART_NEXT_SLATE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_prime_smart_slate",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
