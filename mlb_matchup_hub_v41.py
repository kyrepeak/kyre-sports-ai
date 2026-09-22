"""MLB Matchup Explorer V4.5 — complete Matchup Intelligence V2 Steps 1-12."""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v28 as clean
import mlb_matchup_hub_v29 as frozen_v1
import mlb_matchup_hub_v30 as step1_hub
import mlb_matchup_hub_v32 as step3_hub
import mlb_matchup_hub_v33 as step4_hub
import mlb_matchup_hub_v34 as step5_hub
import mlb_matchup_hub_v35 as step6_hub
import mlb_matchup_hub_v36 as step7_hub
import mlb_matchup_hub_v37 as step8_hub
import mlb_matchup_hub_v38 as step9_hub
import mlb_matchup_hub_v39 as step10_hub
import mlb_matchup_hub_v40 as step11_hub
import mlb_matchup_player_v35 as player_layer
import mlb_matchup_rankings_v21 as rankings

VERSION = "MLB Matchup Hub V4.5 • Intelligence V2 Step 12 FINAL"
FROZEN_MATCHUP_CHAIN = frozen_v1.FROZEN_MATCHUP_CHAIN
FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")

_TECHNICAL_CAPTION_MARKERS = clean._TECHNICAL_CAPTION_MARKERS

_STEP12_CSS = r"""
<style>
.mxv2-step12{border-left:4px solid #7ee2a8;background:linear-gradient(180deg,#101913 0%,#0b100d 100%)}
.mxv2-step12 .mxv2-finalhero{border:1px solid #3d8f60;background:#0c1f14}
.mxv2-step12 .mxv2-finalhero b{font-size:1.08rem;color:#effff4}
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
        + step6_hub._STEP6_CSS
        + step7_hub._STEP7_CSS
        + step8_hub._STEP8_CSS
        + step9_hub._STEP9_CSS
        + step10_hub._STEP10_CSS
        + step11_hub._STEP11_CSS
        + _STEP12_CSS,
        unsafe_allow_html=True,
    )
    st.caption("🧠 Matchup Intelligence V2 COMPLETE • Steps 1-12 active • final calibration/intelligence live • V1 frozen as rollback.")

    original_caption = st.caption
    st.caption = _filtered_caption(original_caption)
    try:
        player_layer.render_player_layer(games_df, section_header, status_info, team_logo, h)
    finally:
        st.caption = original_caption

    with st.expander("🏅 Daily Top 5 — 1+ Hit rankings", expanded=False):
        st.caption("Daily Top 5 remains intentionally frozen on the certified V1 ranking engine until a separately certified V2 ranking migration.")
        rankings.render_daily_rankings(games_df)


__all__ = ["FROZEN_MATCHUP_CHAIN", "FROZEN_V1_PRESENTATION", "VERSION", "render_matchup_hub"]
