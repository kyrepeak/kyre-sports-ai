"""MLB Matchup Explorer V3.6 — Matchup Intelligence V2 Steps 1-3."""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v28 as clean
import mlb_matchup_hub_v29 as frozen_v1
import mlb_matchup_hub_v30 as step1_hub
import mlb_matchup_player_v26 as player_layer
import mlb_matchup_rankings_v21 as rankings

VERSION = "MLB Matchup Hub V3.6 • Intelligence V2 Step 3"
FROZEN_MATCHUP_CHAIN = frozen_v1.FROZEN_MATCHUP_CHAIN
FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")

_TECHNICAL_CAPTION_MARKERS = clean._TECHNICAL_CAPTION_MARKERS

_STEP3_CSS = r"""
<style>
.mxv2-step3{border-left:4px solid #ffb45d}
.mxv2-statgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;margin:8px 0 4px}
.mxv2-mini{border:1px solid #2d435d;background:#0a1725;border-radius:11px;padding:8px 9px;min-width:0}
.mxv2-mini span{display:block;color:#7f99b1;font-size:.50rem;text-transform:uppercase;letter-spacing:.06em;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mxv2-mini b{display:block;color:#f6f9ff;font-size:.91rem;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(max-width:760px){.mxv2-statgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
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
    st.markdown(clean._CSS + step1_hub._EXTRA_CSS + _STEP3_CSS, unsafe_allow_html=True)
    st.caption("🧠 Matchup Intelligence V2 rebuild • Steps 1-3 active • V1 model frozen as rollback.")

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
