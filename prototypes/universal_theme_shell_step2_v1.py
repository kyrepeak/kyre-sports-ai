"""Standalone Step 2 universal-shell demo. Not connected to production."""
from __future__ import annotations

import streamlit as st

from kyre_universal_shell_v1 import build_universal_shell

st.set_page_config(page_title="KYRE Universal Shell • Step 2", layout="wide")

demo = """
<section class="kyre-theme-surface" style="padding:24px">
  <div style="font-size:.72rem;color:var(--kyre-glacier);font-weight:900;letter-spacing:.12em">UNIVERSAL THEME • STEP 2</div>
  <h1 style="margin:6px 0 8px">Black + Glacier Blue Shell</h1>
  <p style="margin:0;color:var(--kyre-text-secondary)">Standalone shell proof. Production pages are not connected.</p>
</section>
"""

st.markdown(
    build_universal_shell(
        demo,
        active_nav="Passing Yards",
        slate_label="Current Slate",
        sport_label="NFL",
    ),
    unsafe_allow_html=True,
)
