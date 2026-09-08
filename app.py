"""Kyre Sports AI Streamlit entrypoint — additive clean presentation router.

Router V10 preserves the frozen Router V9/V8/V7/V6/V5/V4/V3/V2 chain down to
the `streamlit_memory_lazy_router_v1` bootstrap. Only MLB Moneyline advances to
additive V17.2 Step 6; Step 5L live mode, Matchup Explorer and Hits remain frozen.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v10 import render_app


render_app()
