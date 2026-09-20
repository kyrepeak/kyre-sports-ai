"""Passing Yards layered hub — Step 8 final standalone prototype.

Certification assembly only. This entrypoint is intentionally separate from
the frozen production Passing Yards route.
"""
from __future__ import annotations
import streamlit as st

from prototypes.passing_yards_layered_hub_shell_v1 import build_universal_shell
from prototypes.passing_yards_layered_hub_header_v1 import build_passing_yards_header
from prototypes.passing_yards_layered_hub_qb_cards_v1 import QBCard, build_qb_cards
from prototypes.passing_yards_layered_hub_tabs_v1 import build_layered_tabs
from prototypes.passing_yards_layered_hub_previews_v1 import build_hub_previews
from prototypes.passing_yards_layered_hub_responsive_v1 import build_responsive_polish

FINAL_STEP = 8
FINAL_VERSION = "PASSING YARDS LAYERED HUB • STEP 8 • FINAL CERT"

st.set_page_config(page_title="Passing Yards Hub • Final Prototype", layout="wide")

cards = [
    QBCard("Quarterback A","TEAM A","TEAM B","Away","Sun • 1:00 PM ET","Available"),
    QBCard("Quarterback B","TEAM C","TEAM D","Home","Sun • 4:25 PM ET","Available"),
]

content = (
    build_responsive_polish()
    + build_passing_yards_header()
    + build_layered_tabs()
    + build_qb_cards(cards)
    + build_hub_previews()
)

st.markdown(build_universal_shell(content), unsafe_allow_html=True)
