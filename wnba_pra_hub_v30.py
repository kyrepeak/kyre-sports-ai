"""WNBA PRA V3.0 — Step 7 matchup/pace grading route.

WNBA-only. MLB V2.1.7 remains frozen on mlb-v217-frozen-20260818.
Keeps the proven Steps 1-6 stack, adds capped recent-pace/opponent-defense
adjustments, and still leaves final 5M/10M Monte Carlo for the next step.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v29 as previous
import wnba_pra_matchup_v30 as matchup
import wnba_sportsgameodds_v1 as wnba_sgo

MODEL_VERSION = "PRA V3.0"
MLB_FROZEN_BASELINE = previous.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = previous.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption(
        "🧭 PRA V3.0 • Step 7 matchup + pace adjustment ACTIVE • SportsGameOdds WNBA • "
        "MLB V2.1.7 frozen"
    )

    # Render the proven Steps 1-5 shell once. V3.0 owns all sections beneath it
    # so the API bridge and market boards are not duplicated.
    result = previous.previous.v28.render_wnba_pra_hub(section_header, status_info, team_logo, h)

    day = st.session_state.get("wnba_pra_v2_date")
    if not day:
        st.caption("🧭 Select a WNBA slate date to verify markets and run Steps 6-7.")
        return result

    # Reuse the same cached SportsGameOdds snapshot. Step 6 stays visible as the
    # transport/calibration checkpoint; Step 7 shows the matchup-adjusted board.
    wnba_sgo.render_market_panel(day)
    previous.market.render_pra_market_grade(day)
    matchup.render_matchup_grade(day)
    return result


__all__ = [
    "MODEL_VERSION",
    "MLB_FROZEN_BASELINE",
    "MLB_FROZEN_BRANCH",
    "render_wnba_pra_hub",
]
