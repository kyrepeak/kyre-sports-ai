"""Spread V15.4: V15.3.1 projections/backtest plus current live sportsbook board."""

import streamlit as st

import spread_hub_v153 as base
from live_odds_feed import render_live_slate_board

MODEL_VERSION = "V15.4"


def render_spread_hub(games_df, section_header, status_info, team_logo, h):
    st.caption("📡 V15.4 adds current live sportsbook ML / run-line / total prices above the spread tools. Live state-aware modeling lives in V19.1.")
    render_live_slate_board(games_df, title="Live MLB Moneyline • Run Line • Total")
    base.render_spread_hub(games_df, section_header, status_info, team_logo, h)
