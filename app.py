"""Kyre Sports AI Streamlit entrypoint — CFB Step 6 Moneyline Final.

Router V30 preserves the frozen Router V29/V28/V27/.../V2 chain down to the
`streamlit_memory_lazy_router_v1` bootstrap.

Additive Step 6 change:
- preserves permanently frozen CFB Steps 1–5,
- preserves both certified CFB schedule/data hotfixes,
- advances only College Football -> Moneyline to final structural synthesis,
- keeps sportsbook probability weight exactly 0%,
- keeps Over/Under, Game Total, MLB, WNBA, and NFL unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V30_CFB_STEP6_2026-09-08T16:20Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v30 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V30_CFB_STEP6_2026-09-08T16:20Z"


render_app()
