"""Kyre Sports AI Streamlit entrypoint — College Football Step 2.

Router V24 preserves the frozen Router V23/V22/.../V2 chain down to the
`streamlit_memory_lazy_router_v1` bootstrap.

Additive Step 2 change:
- preserves the frozen College Football Step 1 section/page foundation,
- adds NCAA FBS schedule + stable game identity through new versioned modules,
- adds ESPN venue/status enrichment without changing betting-model math,
- keeps every existing MLB/WNBA/NFL route unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V24_CFB_STEP2_2026-09-08T07:30Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v24 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V24_CFB_STEP2_2026-09-08T07:30Z"


render_app()
