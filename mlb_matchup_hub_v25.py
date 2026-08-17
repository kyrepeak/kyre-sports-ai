"""MLB Matchup Explorer V2.5 — BvP Steps 1-3 + fast/deep rankings."""
from __future__ import annotations

import streamlit as st

import mlb_matchup_player_v19 as player_layer
import mlb_matchup_rankings_v16 as rankings

VERSION = "MLB Matchup Hub V2.5"


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    player_layer.render_player_layer(games_df, section_header, status_info, team_logo, h)
    st.markdown("---")
    rankings.render_daily_rankings(games_df)
    st.caption(f"{VERSION} • BvP Step 1 + named pitcher matchup Step 2 + reliability-weighted Step 3 verdict • fast/deep rankings preserved")
