"""Standalone Step 6 entrypoint. Not wired to production."""
from __future__ import annotations
import streamlit as st
from prototypes.passing_yards_layered_hub_shell_v1 import build_universal_shell
from prototypes.passing_yards_layered_hub_header_v1 import build_passing_yards_header
from prototypes.passing_yards_layered_hub_qb_cards_v1 import QBCard, build_qb_cards
from prototypes.passing_yards_layered_hub_tabs_v1 import build_layered_tabs
from prototypes.passing_yards_layered_hub_previews_v1 import build_hub_previews

st.set_page_config(page_title="Passing Yards Hub Prototype", layout="wide")

cards=[
    QBCard("Quarterback A","TEAM A","TEAM B","Away","Sun • 1:00 PM ET","Available"),
    QBCard("Quarterback B","TEAM C","TEAM D","Home","Sun • 4:25 PM ET","Available"),
]
content=(
    build_passing_yards_header()
    + build_layered_tabs()
    + build_qb_cards(cards)
    + build_hub_previews()
)
st.markdown(build_universal_shell(content), unsafe_allow_html=True)
