"""MLB Matchup Explorer V2.1 — player intelligence + fast/deep rankings."""
from __future__ import annotations

import streamlit as st

import mlb_matchup_hub_v14 as player_base
import mlb_matchup_rankings_v16 as rankings

VERSION = "MLB Matchup Hub V2.1"


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    player_base.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    st.markdown("---")
    rankings.render_daily_rankings(games_df)
    st.caption(f"{VERSION} • player intelligence preserved • fast core ranking first • optional Top-8 Statcast deep pass • cached profiles reused across markets")
