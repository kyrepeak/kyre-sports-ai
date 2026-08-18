"""WNBA PRA V3.1.1 — Step 8 empirical-covariance hotfix route.

WNBA-only wrapper. MLB V2.1.7 remains frozen on mlb-v217-frozen-20260818.
Keeps the full V3.0/Step-7 stack and replaces only the Step-8 Monte Carlo
empirical variance handoff exposed by V3.1 diagnostics.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v30 as previous
import wnba_pra_monte_carlo_v311 as monte

MODEL_VERSION = "PRA V3.1.1"
MLB_FROZEN_BASELINE = previous.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = previous.MLB_FROZEN_BRANCH


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption(
        "🧬 PRA V3.1.1 • Step 8 empirical covariance handoff FIXED • actual 5M standard / 10M finalist sims • "
        "SportsGameOdds WNBA • MLB V2.1.7 frozen"
    )

    result = previous.render_wnba_pra_hub(section_header, status_info, team_logo, h)

    day = st.session_state.get("wnba_pra_v2_date")
    if not day:
        st.caption("🧬 Select a WNBA slate date before running the covariance-verified Monte Carlo pass.")
        return result

    monte.render_monte_carlo(day)
    return result


__all__ = [
    "MODEL_VERSION",
    "MLB_FROZEN_BASELINE",
    "MLB_FROZEN_BRANCH",
    "render_wnba_pra_hub",
]
