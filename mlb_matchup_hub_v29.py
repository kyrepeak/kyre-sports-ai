"""MLB Matchup Explorer V3.3 — unified mobile intelligence presentation."""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v28 as clean
import mlb_matchup_player_v23 as player_layer
import mlb_matchup_rankings_v21 as rankings

VERSION = "MLB Matchup Hub V3.3 Unified UI"
FROZEN_MATCHUP_CHAIN = clean.FROZEN_MATCHUP_CHAIN

_TECHNICAL_CAPTION_MARKERS = clean._TECHNICAL_CAPTION_MARKERS

_EXTRA_CSS = r"""
<style>
/* Unified Matchup Intelligence presentation only. */
div[data-testid="stExpander"] details > summary p{font-weight:850!important}
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
    st.caption("🔒 Matchup models frozen • compact snapshot + one full intelligence panel.")

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


__all__ = ["FROZEN_MATCHUP_CHAIN", "VERSION", "render_matchup_hub"]
