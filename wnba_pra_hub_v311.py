"""WNBA PRA V3.1.1 — Step 8 empirical-covariance hotfix route.

WNBA-only wrapper. MLB V2.1.7 remains frozen on mlb-v217-frozen-20260818.
Keeps the full V3.0/Step-7 stack and replaces only the Step-8 Monte Carlo
empirical variance handoff exposed by V3.1 diagnostics.

UI clarity patch: PRA Monte Carlo controls are explicitly labeled PRA so they
cannot be confused with the separate Points 5M/10M production controls. No
simulation, projection, grading, persistence, or qualification math changes.
"""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v30 as previous
import wnba_pra_monte_carlo_v311 as monte

MODEL_VERSION = "PRA V3.1.1"
MLB_FROZEN_BASELINE = previous.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = previous.MLB_FROZEN_BRANCH


def _render_pra_monte_carlo_labeled(day):
    """Relabel only the inherited PRA Step-8 controls during this render."""
    original_button = st.button
    original_info = st.info

    def _pra_button(label, *args, **kwargs):
        text = str(label)
        if text == "🚀 RUN 5,000,000 STANDARD SIMS":
            label = "🚀 RUN PRA 5,000,000 STANDARD SIMS"
        elif text == "🏁 RUN 10,000,000 FINAL / CLOSE-CALL SIMS":
            label = "🏁 RUN PRA 10,000,000 FINAL / CLOSE-CALL SIMS"
        return original_button(label, *args, **kwargs)

    def _pra_info(body, *args, **kwargs):
        text = str(body)
        if text.startswith("Step 8 is armed but has not claimed any simulations yet."):
            body = (
                "PRA Step 8 is armed but has not claimed any PRA simulations yet. "
                "Tap RUN PRA 5,000,000 STANDARD SIMS to execute the PRA production pass. "
                "This is separate from the Points 5M simulation on the Points page."
            )
        return original_info(body, *args, **kwargs)

    st.button = _pra_button
    st.info = _pra_info
    try:
        return monte.render_monte_carlo(day)
    finally:
        st.button = original_button
        st.info = original_info


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

    _render_pra_monte_carlo_labeled(day)
    return result


__all__ = [
    "MODEL_VERSION",
    "MLB_FROZEN_BASELINE",
    "MLB_FROZEN_BRANCH",
    "render_wnba_pra_hub",
]
