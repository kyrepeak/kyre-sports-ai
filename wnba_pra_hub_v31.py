"""WNBA PRA V3.1 — Step 8 production Monte Carlo route.

WNBA-only wrapper. MLB V2.1.7 remains frozen on mlb-v217-frozen-20260818.
Keeps the proven V3.0 schedule/roster/context/availability/minutes-role/matchup
and exact SportsGameOdds grading stack, then appends the actual 5M/10M Monte
Carlo execution layer. No frozen MLB production module is changed here.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v30 as previous
import wnba_pra_monte_carlo_v31 as monte

MODEL_VERSION = "PRA V3.1"
MLB_FROZEN_BASELINE = previous.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = previous.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption(
        "🎲 PRA V3.1 • Step 8 production Monte Carlo ACTIVE • actual 5M standard / 10M finalist sims • "
        "SportsGameOdds WNBA • MLB V2.1.7 frozen"
    )

    # V3.0 owns Steps 1-7 and exact-market visibility.
    result = previous.render_wnba_pra_hub(section_header, status_info, team_logo, h)

    day = st.session_state.get("wnba_pra_v2_date")
    if not day:
        st.caption("🎲 Select a WNBA slate date before running production Monte Carlo.")
        return result

    monte.render_monte_carlo(day)
    return result


__all__ = [
    "MODEL_VERSION",
    "MLB_FROZEN_BASELINE",
    "MLB_FROZEN_BRANCH",
    "render_wnba_pra_hub",
]
