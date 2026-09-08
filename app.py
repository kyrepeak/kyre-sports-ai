"""Kyre Sports AI Streamlit entrypoint — CFB Step 8 Over/Under Model V1.

Router V32 preserves the permanently frozen Router V31/V30/.../V2 chain down
to the streamlit_memory_lazy_router_v1 bootstrap.

Additive Step 8 change:
- preserves permanently frozen CFB Steps 1-7,
- preserves College Football Moneyline Step 6 unchanged,
- advances only College Football -> Over/Under to raw projected-total modeling,
- keeps sportsbook/market projection weight at 0%,
- keeps Top-5/final ranking OFF until Step 9,
- keeps Game Total, MLB, WNBA, and NFL unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V32_CFB_STEP8_2026-09-08T17:20Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v32 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V32_CFB_STEP8_2026-09-08T17:20Z"


render_app()
