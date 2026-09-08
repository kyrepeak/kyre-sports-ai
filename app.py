"""Kyre Sports AI Streamlit entrypoint — additive Hits Step 4 router.

Router V19 preserves the frozen Router V18/V17/V16/V15/V14/V13/V12/V11/V10/V9/V8/V7/V6/V5/V4/V3/V2
chain down to the `streamlit_memory_lazy_router_v1` bootstrap. MLB Moneyline
remains permanently frozen on V17.8 Step 12. Only MLB 1+ Hit advances to
V13.19 Step 4 favorable matchup selection; Matchup Explorer and all other
markets remain unchanged.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v19 import render_app


render_app()
