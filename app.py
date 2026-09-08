"""Kyre Sports AI Streamlit entrypoint — strict no-TOUGH Hits hotfix.

Router V21 preserves the frozen Router V20/V19/V18/V17/V16/V15/V14/V13/V12/V11/V10/V9/V8/V7/V6/V5/V4/V3/V2
chain down to the `streamlit_memory_lazy_router_v1` bootstrap. MLB Moneyline
remains frozen on V17.8 Step 12. Only MLB 1+ Hit advances to V13.21 strict
no-TOUGH visible selection; Matchup Explorer and all other markets remain
unchanged.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v21 import render_app


render_app()
