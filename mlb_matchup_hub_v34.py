"""MLB Matchup Explorer V3.8 — Matchup Intelligence V2 Steps 1-5."""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v28 as clean
import mlb_matchup_hub_v29 as frozen_v1
import mlb_matchup_hub_v30 as step1_hub
import mlb_matchup_hub_v32 as step3_hub
import mlb_matchup_hub_v33 as step4_hub
import mlb_matchup_player_v28 as player_layer
import mlb_matchup_rankings_v21 as rankings

VERSION = "MLB Matchup Hub V3.8 • Intelligence V2 Step 5"
FROZEN_MATCHUP_CHAIN = frozen_v1.FROZEN_MATCHUP_CHAIN
FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")

_TECHNICAL_CAPTION_MARKERS = clean._TECHNICAL_CAPTION_MARKERS

_STEP5_CSS = r"""
<style>
.mxv2-step5{border-left:4px solid #55b7ff}
.mxv2-pitchhead{font-size:.60rem;font-weight:900;letter-spacing:.08em;color:#8ea8c1;margin:7px 0 6px}
.mxv2-pitchrow{display:grid;grid-template-columns:1.55fr repeat(8,minmax(0,.7fr));gap:6px;border:1px solid #24384d;background:#08131f;border-radius:10px;padding:8px;margin:6px 0;align-items:center}
.mxv2-pitchrow div{min-width:0}
.mxv2-pitchrow b{display:block;color:#f6f9ff;font-size:.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mxv2-pitchrow span{display:block;color:#7890a6;font-size:.48rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
@media(max-width:900px){.mxv2-pitchrow{grid-template-columns:repeat(3,minmax(0,1fr))}.mxv2-pitchrow>div:first-child{grid-column:1/-1}}
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
        + _STEP5_CSS,
        unsafe_allow_html=True,
    )
    st.caption("🧠 Matchup Intelligence V2 rebuild • Steps 1-5 active • V1 model frozen as rollback.")

    original_caption = st.caption
    st.caption = _filtered_caption(original_caption)
    try:
        player_layer.render_player_layer(
            games_df,
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        st.caption = original_caption

    with st.expander("🏅 Daily Top 5 — 1+ Hit rankings", expanded=False):
        rankings.render_daily_rankings(games_df)


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_V1_PRESENTATION",
    "VERSION",
    "render_matchup_hub",
]
