"""Kyre Sports AI Streamlit entrypoint — additive clean presentation router.

Router V8 preserves the frozen Router V7/V6/V5/V4/V3/V2 chain down to the
`streamlit_memory_lazy_router_v1` bootstrap. Only MLB Moneyline advances to
additive UI V17.0 Step 5; Matchup Explorer and Hits remain frozen.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v8 import render_app


render_app()
