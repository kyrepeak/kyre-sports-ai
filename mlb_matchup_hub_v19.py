"""MLB Matchup Explorer V1.9 — V1.4 player intelligence + V1.4 Statcast-aware rankings."""
from __future__ import annotations

import streamlit as st

import mlb_matchup_hub_v14 as base
import mlb_matchup_rankings_v14 as rankings

VERSION = "MLB Matchup Hub V1.9"


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    base.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    st.markdown("---")
    rankings.render_daily_rankings(games_df)
    st.caption(f"{VERSION} • V1.4 player intelligence preserved • verified Statcast contact quality + platoon + starter pitch-mix enrichment added to full-slate rankings • all deep context remains capped and auditable")
