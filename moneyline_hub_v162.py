"""Moneyline V16.2: V16.1 projections plus current live sportsbook board."""

import streamlit as st

import moneyline_hub_v161 as base
from live_odds_feed import render_live_slate_board

MODEL_VERSION = "V16.2"


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    st.caption("📡 V16.2 adds a live sportsbook market layer. Pregame model probabilities remain independent from sportsbook prices.")
    render_live_slate_board(games_df, title="Live MLB Moneyline • Run Line • Total")
    base.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
