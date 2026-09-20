"""Standalone Step 4 entrypoint. Not wired to production."""
from __future__ import annotations
import streamlit as st
from prototypes.passing_yards_layered_hub_shell_v1 import build_universal_shell
from prototypes.passing_yards_layered_hub_header_v1 import build_passing_yards_header
from prototypes.passing_yards_layered_hub_qb_cards_v1 import QBCard, build_qb_cards

st.set_page_config(page_title="Passing Yards Hub Prototype", layout="wide")

demo_cards = [
    QBCard("Quarterback A", "TEAM A", "TEAM B", "Away", "Sun • 1:00 PM ET", "Available"),
    QBCard("Quarterback B", "TEAM C", "TEAM D", "Home", "Sun • 4:25 PM ET", "Available"),
]
content = build_passing_yards_header() + build_qb_cards(demo_cards)
st.markdown(build_universal_shell(content), unsafe_allow_html=True)
