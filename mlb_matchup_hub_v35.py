"""MLB Matchup Explorer V3.9 — Matchup Intelligence V2 Steps 1-6."""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v28 as clean
import mlb_matchup_hub_v29 as frozen_v1
import mlb_matchup_hub_v30 as step1_hub
import mlb_matchup_hub_v32 as step3_hub
import mlb_matchup_hub_v33 as step4_hub
import mlb_matchup_hub_v34 as step5_hub
import mlb_matchup_player_v29 as player_layer
import mlb_matchup_rankings_v21 as rankings

VERSION = "MLB Matchup Hub V3.9 • Intelligence V2 Step 6"
FROZEN_MATCHUP_CHAIN = frozen_v1.FROZEN_MATCHUP_CHAIN
FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")

_TECHNICAL_CAPTION_MARKERS = clean._TECHNICAL_CAPTION_MARKERS

_STEP6_CSS = r"""
<style>
.mxv2-step6{border-left:4px solid #ff6f91}
</style>
"""


def _filtered_caption(original):
    def wrapped(body: Any, *args: Any, **kwargs: Any):
        text = str(body or "")
        if any(marker in text for marker in _TECHNICAL_CAPTION_MARKERS):
            return None
        return original(body, *args, **kwargs)
    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(
        clean._CSS
        + step1_hub._EXTRA_CSS
        + step3_hub._STEP3_CSS
        + step4_hub._STEP4_CSS
        + step5_hub._STEP5_CSS
        + _STEP6_CSS,
        unsafe_allow_html=True,
    )
    st.caption("🧠 Matchup Intelligence V2 rebuild • Steps 1-6 active • V1 model frozen as rollback.")

    original_caption = st.caption
    st.caption = _filtered_caption(original_caption)
    try:
        player_layer.render_player_layer(games_df, section_header, status_info, team_logo, h)
    finally:
        st.caption = original_caption

    with st.expander("🏅 Daily Top 5 — 1+ Hit rankings", expanded=False):
        rankings.render_daily_rankings(games_df)


__all__ = ["FROZEN_MATCHUP_CHAIN", "FROZEN_V1_PRESENTATION", "VERSION", "render_matchup_hub"]
