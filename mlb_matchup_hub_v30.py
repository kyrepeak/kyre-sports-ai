"""MLB Matchup Explorer V3.4 — V2 Step 1 foundation presentation.

Presentation router for the redesigned Matchup Intelligence V2 card. The current
V1 model chain remains frozen; this layer only adds Step 1 data-quality/gating UI.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v28 as clean
import mlb_matchup_hub_v29 as frozen_v1
import mlb_matchup_player_v24 as player_layer
import mlb_matchup_rankings_v21 as rankings

VERSION = "MLB Matchup Hub V3.4 • Intelligence V2 Step 1"
FROZEN_MATCHUP_CHAIN = frozen_v1.FROZEN_MATCHUP_CHAIN
FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")

_TECHNICAL_CAPTION_MARKERS = clean._TECHNICAL_CAPTION_MARKERS

_EXTRA_CSS = r"""
<style>
/* Matchup Intelligence V2 — compact single-player step stack. */
.mxv2-step{border:1px solid #355773;border-radius:18px;background:linear-gradient(145deg,#0b1828,#08131f);padding:15px 16px;margin:8px 0 10px;box-shadow:0 8px 24px rgba(0,0,0,.12)}
.mxv2-step1{border-left:4px solid #54d7ff}
.mxv2-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
.mxv2-kicker{color:#63dfff;font-size:.62rem;font-weight:950;letter-spacing:.11em;text-transform:uppercase;line-height:1.35}
.mxv2-badge{border:1px solid #3d617d;border-radius:999px;padding:5px 8px;color:#dcecf7;background:#0b1c2b;font-size:.53rem;font-weight:950;white-space:nowrap}
.mxv2-lead{color:#f8fbff;font-size:1.04rem;line-height:1.35;margin-top:9px}
.mxv2-status{color:#9eb3c9;font-size:.69rem;font-weight:800;margin-top:4px;line-height:1.4}
.mxv2-rule{height:1px;background:#29445c;margin:11px 0}
.mxv2-row{color:#d6e1ec;font-size:.70rem;line-height:1.58;margin:6px 0;overflow-wrap:anywhere}
.mxv2-row b{color:#f4f8fc}.mxv2-muted{color:#839bb1;font-size:.60rem}
div[data-testid="stExpander"] details > summary p{font-weight:850!important}
@media(max-width:640px){
  .mxv2-top{display:block}.mxv2-badge{display:inline-block;margin-top:7px}.mxv2-lead{font-size:.98rem}.mxv2-row{font-size:.67rem}
}
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
    st.markdown(clean._CSS + _EXTRA_CSS, unsafe_allow_html=True)
    st.caption("🧠 Matchup Intelligence V2 rebuild • Step 1 foundation active • V1 model frozen as rollback.")

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
