"""Kyre Sports AI Streamlit entrypoint — additive clean presentation router.

Router V7 preserves the frozen Router V6/V5/V4/V3/V2 chain down to the
`streamlit_memory_lazy_router_v1` bootstrap. Only MLB Moneyline advances to
additive UI V16.9 Step 4; Matchup Explorer and Hits remain frozen.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v7 import render_app


render_app()
