"""MLB Matchup Explorer V1.6 — V1.4 player intelligence + matchup-calibrated daily rankings."""
from __future__ import annotations

import streamlit as st

import mlb_matchup_hub_v14 as base
import mlb_matchup_rankings_v11 as rankings

VERSION = "MLB Matchup Hub V1.6"


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    base.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    st.markdown("---")
    rankings.render_daily_rankings(games_df)
    st.caption(f"{VERSION} • V1.4 player intelligence preserved • matchup-calibrated full-slate Top 5 rankings • unsupported context layers stay explicitly pending")
