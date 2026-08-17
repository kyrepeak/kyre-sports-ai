"""MLB Matchup Explorer V3.1 — BvP Steps 1-5 + strict-budget rankings + team logos."""
from __future__ import annotations

import streamlit as st

import mlb_matchup_player_v21 as player_layer
import mlb_matchup_rankings_v21 as rankings

VERSION = "MLB Matchup Hub V3.1"


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    player_layer.render_player_layer(games_df, section_header, status_info, team_logo, h)
    st.markdown("---")
    rankings.render_daily_rankings(games_df)
    st.caption(f"{VERSION} • Steps 1-5 preserved • Daily 1+ Hit Top 5 uses reliability-gated player intelligence • strict-budget deep micro-pass • team logos beside player names")
