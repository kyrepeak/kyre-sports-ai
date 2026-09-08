"""Kyre Sports AI Streamlit entrypoint — CFB Step 9 Over/Under Final Ranking.

Router V33 preserves the permanently frozen Router V32/V31/.../V2 chain down
to the streamlit_memory_lazy_router_v1 bootstrap.

Additive Step 9 change:
- preserves permanently frozen CFB Steps 1-8,
- preserves College Football Moneyline Step 6 unchanged,
- completes College Football -> Over/Under with final O/U/PASS rules + Top-5,
- keeps analysis-line projection weight at 0%,
- keeps sportsbook feed/price, market probability, edge/EV, and Monte Carlo out,
- keeps Game Total, MLB, WNBA, and NFL unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V33_CFB_STEP9_2026-09-08T17:45Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v33 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V33_CFB_STEP9_2026-09-08T17:45Z"


render_app()
