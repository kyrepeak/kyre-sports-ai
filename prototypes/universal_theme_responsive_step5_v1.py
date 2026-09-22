"""Standalone Step 5 responsive showcase. Not connected to production."""
from __future__ import annotations

import streamlit as st

from kyre_universal_components_v1 import build_component_showcase
from kyre_universal_responsive_v1 import build_responsive_css
from kyre_universal_shell_v1 import build_universal_shell

st.set_page_config(page_title="KYRE Responsive • Step 5", layout="wide")

content = build_responsive_css() + build_component_showcase()
st.markdown(
    build_universal_shell(
        content,
        active_nav="Passing Yards",
        slate_label="Responsive Lab",
        sport_label="NFL",
    ),
    unsafe_allow_html=True,
)
