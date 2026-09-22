"""MLB Matchup Explorer V2.0 — V1.4 player intelligence + repaired V1.9 ranking feeds."""
from __future__ import annotations

import streamlit as st

import mlb_matchup_hub_v14 as player_base
import mlb_matchup_rankings_v15 as rankings

VERSION = "MLB Matchup Hub V2.0"


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    player_base.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    st.markdown("---")
    rankings.render_daily_rankings(games_df)
    st.caption(f"{VERSION} • player intelligence preserved • Statcast details-query repaired • bullpen recent-game parser hardened with live-feed fallback • projection math/caps unchanged")
