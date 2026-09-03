"""Kyre Sports AI Streamlit entrypoint — additive clean presentation router.

Router V5 preserves the frozen Router V4/V3/V2/V1 chain. Only MLB Moneyline
advances to additive UI V16.7 Step 2; Matchup Explorer and Hits remain frozen.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v5 import render_app


render_app()
