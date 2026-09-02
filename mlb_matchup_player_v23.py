"""MLB Matchup Explorer player presentation V2.3.

Presentation-only wrapper that keeps the compact Matchup Snapshot visible while
placing the complete frozen detailed Matchup Explorer chain inside one closed
Full Matchup Intelligence panel. No projection, probability, calibration,
ranking, selection, or fair-odds math is implemented here.
"""
from __future__ import annotations

import streamlit as st

import mlb_matchup_player_v20 as frozen_detail
import mlb_matchup_player_v22 as clean

VERSION = "MLB Player Intelligence V2.3 Unified UI"
FROZEN_PLAYER_CHAIN = clean.FROZEN_PLAYER_CHAIN
FULL_INTELLIGENCE_LABEL = "🧠 Full Matchup Intelligence — all steps"


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Keep the compact snapshot visible and group every detailed step together."""
    # Reserve the compact summary above the detailed panel. The frozen detail
    # chain still runs exactly as before so Step 4/Step 5 state stays identical.
    snapshot_slot = st.empty()

    original_caption = st.caption
    st.caption = clean._filtered_caption(original_caption)
    try:
        with st.expander(FULL_INTELLIGENCE_LABEL, expanded=False):
            st.caption("Open this panel for the complete matchup audit trail and every detailed step.")
            frozen_detail.render_player_layer(
                games_df,
                section_header,
                status_info,
                team_logo,
                h,
            )
    finally:
        st.caption = original_caption

    # Reuse the already-certified compact snapshot presentation. It reads the
    # frozen Step 4 state produced above and performs no model mutation.
    clean._render_snapshot(snapshot_slot, games_df)


__all__ = [
    "FROZEN_PLAYER_CHAIN",
    "FULL_INTELLIGENCE_LABEL",
    "VERSION",
    "render_player_layer",
]
