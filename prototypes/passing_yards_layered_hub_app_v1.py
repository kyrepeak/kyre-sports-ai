"""Standalone Streamlit entrypoint for the Passing Yards layered prototype.

This file is intentionally NOT wired into production routing.
"""
from __future__ import annotations
import streamlit as st
from prototypes.passing_yards_layered_hub_shell_v1 import build_universal_shell

st.set_page_config(page_title="Passing Yards Hub Prototype", layout="wide")
st.markdown(
    build_universal_shell(
        '<div class="ks-shell-slotnote" data-prototype-main-slot="true">'
        'Passing Yards Hub • Step 2 shell'
        '</div>'
    ),
    unsafe_allow_html=True,
)
