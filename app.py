"""Kyre Sports AI Streamlit entrypoint — College Football Step 4 Moneyline UI.

Router V26 preserves the frozen Router V25/V24/V23/.../V2 chain down to the
`streamlit_memory_lazy_router_v1` bootstrap.

Additive Step 4 change:
- preserves permanently frozen College Football Steps 1–3,
- advances only College Football -> Moneyline to a dedicated page UI,
- keeps Over/Under and Game Total on frozen Step 3,
- keeps all CFB model/probability/simulation outputs disabled,
- keeps every existing MLB/WNBA/NFL route unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V26_CFB_STEP4_2026-09-08T00:30Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v26 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V26_CFB_STEP4_2026-09-08T00:30Z"


render_app()
