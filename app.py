"""Kyre Sports AI Streamlit entrypoint — College Football Step 5 Moneyline Model V1.

Router V27 preserves the frozen Router V26/V25/V24/V23/.../V2 chain down to
the `streamlit_memory_lazy_router_v1` bootstrap.

Additive Step 5 change:
- preserves permanently frozen College Football Steps 1–4,
- advances only College Football -> Moneyline to raw pre-calibration Model V1,
- keeps Over/Under and Game Total on frozen prior routes,
- keeps sportsbook prices, fair moneyline, edge/EV, final pick grading and
  Monte Carlo OFF,
- keeps every existing MLB/WNBA/NFL route unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V27_CFB_STEP5_2026-09-08T07:15Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v27 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V27_CFB_STEP5_2026-09-08T07:15Z"


render_app()
