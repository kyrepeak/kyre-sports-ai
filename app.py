"""Kyre Sports AI Streamlit entrypoint — College Football Step 1.

Router V23 preserves the frozen Router V22/V21/V20/V19/V18/V17/V16/V15/V14/V13/V12/V11/V10/V9/V8/V7/V6/V5/V4/V3/V2
chain down to the `streamlit_memory_lazy_router_v1` bootstrap.

Additive Step 1 change:
- adds College Football as a fourth sport,
- exposes Moneyline, Over/Under, and Game Total page foundations,
- keeps every existing MLB/WNBA/NFL route unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V23_CFB_STEP1_2026-09-08T06:40Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v23 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V23_CFB_STEP1_2026-09-08T06:40Z"


render_app()
