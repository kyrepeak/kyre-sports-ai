"""WNBA PRA V2.9 — Step 6 exact SportsGameOdds PRA grading.

WNBA-only route. MLB V2.1.7 remains frozen on mlb-v217-frozen-20260818.
Keeps the proven V2.8.4 WNBA schedule/roster/context/availability/minutes-role
layers, then adds Step 6 exact sportsbook grading. No MLB production/model module
is imported or modified here.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v284 as previous
import wnba_pra_market_v29 as market
import wnba_sportsgameodds_v1 as wnba_sgo

MODEL_VERSION = "PRA V2.9"
MLB_FROZEN_BASELINE = previous.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = previous.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption(
        "🎯 PRA V2.9 • Step 6 exact market grading ACTIVE • SportsGameOdds WNBA • "
        "MLB V2.1.7 frozen"
    )

    # Render the proven Step 1-5 WNBA shell directly from V2.8's current engine.
    # Avoid calling previous.render_wnba_pra_hub because V2.8.4 itself appends
    # the API panel; V2.9 owns the post-shell market sections to prevent duplicates.
    result = previous.v28.render_wnba_pra_hub(section_header, status_info, team_logo, h)

    day = st.session_state.get("wnba_pra_v2_date")
    if not day:
        st.caption("🎯 Select a WNBA slate date to verify SportsGameOdds markets and run Step 6 grading.")
        return result

    # Transport visibility first, then the model-vs-market layer. The same cached
    # SportsGameOdds response is reused, so Step 6 does not multiply provider calls.
    wnba_sgo.render_market_panel(day)
    market.render_pra_market_grade(day)
    return result


__all__ = [
    "MODEL_VERSION",
    "MLB_FROZEN_BASELINE",
    "MLB_FROZEN_BRANCH",
    "render_wnba_pra_hub",
]
