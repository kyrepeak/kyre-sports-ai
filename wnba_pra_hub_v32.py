"""WNBA PRA V3.2 — Step 9 Final Decision + Daily Master Card route.

WNBA-only wrapper. MLB V2.1.7 remains frozen on mlb-v217-frozen-20260818.
Keeps the full V3.1.1 verified schedule/roster/context/availability/minutes-role/
matchup/SportsGameOdds/empirical-correlated Monte Carlo stack, then appends the
Step-9 decision layer and future-ready WNBA Daily Master Card.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v311 as previous
import wnba_pra_final_v32 as final

MODEL_VERSION = "PRA V3.2"
MLB_FROZEN_BASELINE = previous.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = previous.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption(
        "🏆 PRA V3.2 • Step 9 Final Decision + WNBA Daily Master Card ACTIVE • "
        "PRA production connector live • SportsGameOdds WNBA • MLB V2.1.7 frozen"
    )

    result = previous.render_wnba_pra_hub(section_header, status_info, team_logo, h)

    day = st.session_state.get("wnba_pra_v2_date")
    if not day:
        st.caption("🏆 Select a WNBA slate date, complete Step 8, then the Final Card will populate automatically.")
        return result

    final.render_final_decision(day)
    return result


__all__ = [
    "MODEL_VERSION",
    "MLB_FROZEN_BASELINE",
    "MLB_FROZEN_BRANCH",
    "render_wnba_pra_hub",
]
