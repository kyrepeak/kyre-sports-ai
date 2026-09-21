"""Standalone Step 3 shared-components demo. Not connected to production."""
from __future__ import annotations

import streamlit as st

from kyre_universal_components_v1 import build_component_showcase
from kyre_universal_shell_v1 import build_universal_shell

st.set_page_config(page_title="KYRE Universal Components • Step 3", layout="wide")

st.markdown(
    build_universal_shell(
        build_component_showcase(),
        active_nav="Passing Yards",
        slate_label="Component Lab",
        sport_label="NFL",
    ),
    unsafe_allow_html=True,
)
