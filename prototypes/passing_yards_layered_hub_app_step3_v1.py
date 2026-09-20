"""Standalone Step 3 entrypoint. Not wired to production."""
from __future__ import annotations
import streamlit as st
from prototypes.passing_yards_layered_hub_shell_v1 import build_universal_shell
from prototypes.passing_yards_layered_hub_header_v1 import build_passing_yards_header

st.set_page_config(page_title="Passing Yards Hub Prototype", layout="wide")
st.markdown(build_universal_shell(build_passing_yards_header()), unsafe_allow_html=True)
