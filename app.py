"""Kyre Sports AI Streamlit entrypoint — CFB Step 11 Game Total Distribution.

Router V35 preserves the permanently frozen Router V34/V33/.../V2 chain down
to the streamlit_memory_lazy_router_v1 bootstrap.

Additive Step 11 change:
- preserves permanently frozen CFB Steps 1-10,
- preserves College Football Moneyline Step 6 unchanged,
- preserves College Football Over/Under Step 9 unchanged,
- advances only College Football -> Game Total to independent distribution modeling,
- keeps sportsbook/market inputs, EV, final pick/ranking, and Monte Carlo OFF,
- keeps MLB, WNBA, and NFL unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V35_CFB_STEP11_2026-09-08T19:02Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v35 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V35_CFB_STEP11_2026-09-08T19:02Z"


render_app()
