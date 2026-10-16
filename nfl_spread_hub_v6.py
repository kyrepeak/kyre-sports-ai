"""NFL Spread V6 — repeatable smart-date repair over frozen V5."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

import nfl_spread_hub_v5 as prior
from nfl_spread_autodate_repair_v1 import apply_spread_autodate


MODEL_VERSION = "NFL SPREAD V6 • REPEATABLE AUTO-DATE • V5 FROZEN"
FROZEN_PRIOR = "nfl_spread_hub_v5"
REPEATABLE_EMPTY_DATE_ADVANCE = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False


def resolve_default_slate(selected):
    return prior.resolve_default_slate(selected)


def render_nfl_hub(market: str = "Spread") -> None:
    if str(market or "") != "Spread":
        raise RuntimeError("NFL Spread V6 only owns the Spread route.")

    today = datetime.now(prior.prior.frozen.base.ET).date()
    apply_spread_autodate(st.session_state, today, resolve_default_slate)

    feedback = st.session_state.pop("nfl_spread_v6_feedback", "")
    if feedback:
        st.info(feedback)

    # V5 keeps ownership of the certified HTML guard, V4 presentation,
    # projection model, market transport and deterministic 5M Monte Carlo.
    prior.render_nfl_hub(market)


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "REPEATABLE_EMPTY_DATE_ADVANCE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "render_nfl_hub",
    "resolve_default_slate",
]
