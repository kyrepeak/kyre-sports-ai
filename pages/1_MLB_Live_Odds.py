"""Native Streamlit page for the certified read-only MLB live odds UI."""
from __future__ import annotations

import streamlit as st

from mlb_live_odds_streamlit_v1 import render_mlb_live_odds_page


st.set_page_config(
    page_title="MLB Live Odds",
    page_icon="⚾",
    layout="wide",
)

render_mlb_live_odds_page()
