"""Kyre Sports AI Streamlit entrypoint — final additive Moneyline router.

Router V16 preserves the frozen Router V15/V14/V13/V12/V11/V10/V9/V8/V7/V6/V5/V4/V3/V2
chain down to the `streamlit_memory_lazy_router_v1` bootstrap. Only MLB
Moneyline advances to additive V17.8 Step 12 Final; Step 5L live mode, Matchup
Explorer and Hits remain frozen.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v16 import render_app


render_app()
