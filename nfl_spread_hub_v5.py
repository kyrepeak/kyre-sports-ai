"""NFL Spread V5 — smart next verified slate over frozen V4 presentation."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

import nfl_spread_hub_v4 as prior
import streamlit_memory_lazy_router_v136 as certified_guard
from nfl_spread_next_slate_v1 import resolve_spread_slate_date

MODEL_VERSION = "NFL SPREAD V5 • SMART NEXT VERIFIED SLATE • V4 FROZEN"
FROZEN_PRIOR = "nfl_spread_hub_v4"
HTML_GUARD_OWNER = "streamlit_memory_lazy_router_v136"
SMART_NEXT_SLATE = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False


def _coerce_day(value: Any, fallback: date) -> date:
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return fallback


def resolve_default_slate(selected: date) -> dict[str, Any]:
    """Resolve an empty day to the next real NFL game date using the fast calendar."""
    return resolve_spread_slate_date(selected, prior.frozen.base.load_nfl_slate)


def _prepare_initial_spread_date(today: date) -> dict[str, Any] | None:
    """Resolve only the initial Spread visit; manual date choices remain user-owned."""
    if st.session_state.get("nfl_spread_v5_auto_resolved"):
        return None
    if "nfl_spread_v4_date_input" in st.session_state:
        st.session_state["nfl_spread_v5_auto_resolved"] = True
        return None

    result = resolve_default_slate(today)
    target = _coerce_day(result.get("resolved_date"), today)
    if result.get("state") != "FOUND":
        target = today

    # Override any stale shared NFL date on first Spread visit. V4 remains the
    # owner of the visible date widget and all later manual selections.
    st.session_state["nfl_v1_date"] = target
    st.session_state["nfl_spread_v4_date_input"] = target
    st.session_state["nfl_spread_v5_auto_resolved"] = True

    if target != today:
        st.session_state["nfl_spread_v5_feedback"] = (
            f"📅 {today.isoformat()} has no NFL games. Opened the next verified slate: {target.isoformat()}."
        )
    return result


def render_nfl_hub(market: str = "Spread") -> None:
    if str(market or "") != "Spread":
        raise RuntimeError("NFL Spread V5 only owns the Spread route.")

    # Reuse the already-certified V136 V4 HTML guard rather than duplicating or
    # weakening the frozen presentation repair.
    certified_guard._install_html_guard(prior)

    today = datetime.now(prior.frozen.base.ET).date()
    _prepare_initial_spread_date(today)

    feedback = st.session_state.pop("nfl_spread_v5_feedback", "")
    if feedback:
        st.info(feedback)

    prior.render_nfl_hub(market)


__all__ = [
    "FROZEN_PRIOR",
    "HTML_GUARD_OWNER",
    "MODEL_VERSION",
    "SMART_NEXT_SLATE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_prepare_initial_spread_date",
    "render_nfl_hub",
    "resolve_default_slate",
]
