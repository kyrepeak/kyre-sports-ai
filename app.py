"""Kyre Sports AI Streamlit entrypoint — additive clean presentation router.

Router V15 preserves the frozen Router V14/V13/V12/V11/V10/V9/V8/V7/V6/V5/V4/V3/V2
chain down to the `streamlit_memory_lazy_router_v1` bootstrap. Only MLB
Moneyline advances to additive V17.7 Step 11; Step 5L live mode, Matchup Explorer
and Hits remain frozen.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v15 import render_app


render_app()
