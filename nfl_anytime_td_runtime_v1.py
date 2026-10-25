"""API2 NFL Anytime TD canonical runtime V1.

Owns only the NFL Anytime TD presentation boundary. Provider selection, market
truth, normalization, fallback, freshness and conflict resolution stay behind
Kyre Sports API and the global Step 2D data-truth gate.
"""
from __future__ import annotations

import streamlit as st


API2_NFL_ANYTIME_TD_CANONICAL_ROUTER_V1_FROZEN = True
MODEL_VERSION = "API2 NFL ANYTIME TD CANONICAL RUNTIME V1"
DATA_GATEWAY = "kyre_sports_api"
DATA_TRUTH_GATE = "api2_step2d_data_truth_gate_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


def render_nfl_anytime_td_runtime() -> None:
    """Render the dedicated Anytime TD boundary without legacy NFL hub fallback."""
    st.markdown("### 🏈 NFL Anytime TD")
    st.caption(
        "Dedicated canonical API2 route • Kyre Sports API gateway • "
        "Step 2D data-truth protected"
    )
    st.info(
        "NFL Anytime TD now has isolated canonical route ownership. "
        "Until a certified Anytime TD market payload is supplied by Kyre Sports API, "
        "this page remains in a semantic unavailable state instead of inventing or "
        "borrowing values from another market."
    )


__all__ = [
    "API2_NFL_ANYTIME_TD_CANONICAL_ROUTER_V1_FROZEN",
    "DATA_GATEWAY",
    "DATA_TRUTH_GATE",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_nfl_anytime_td_runtime",
]
