"""Kyre Sports AI Streamlit entrypoint — CFB Step 12 Final.

Router V36 preserves the permanently frozen Router V35/V34/.../V2 chain down
to the streamlit_memory_lazy_router_v1 bootstrap.

Additive Step 12 change:
- preserves permanently frozen CFB Steps 1-11,
- preserves College Football Moneyline Step 6 unchanged,
- preserves College Football Over/Under Step 9 unchanged,
- completes College Football -> Game Total with final synthesis + Top-5,
- completes the full College Football Steps 1-12 build,
- keeps sportsbook/market inputs, EV, betting picks, and Monte Carlo out of Game Total,
- keeps MLB, WNBA, and NFL unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V36_CFB_STEP12_2026-09-08T19:28Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v36 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V36_CFB_STEP12_2026-09-08T19:28Z"


render_app()
