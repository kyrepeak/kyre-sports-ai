"""Kyre Sports AI Streamlit entrypoint — College Football Step 3.

Router V25 preserves the frozen Router V24/V23/.../V2 chain down to the
`streamlit_memory_lazy_router_v1` bootstrap.

Additive Step 3 change:
- preserves frozen College Football Steps 1–2,
- adds NCAA-derived team records, scoring baselines, recent form, home/away splits,
  opponent-win-percentage schedule strength, official NCAA team-stat enrichment,
  AP ranking context, and explicit data-quality checks,
- keeps all CFB projection/model outputs disabled,
- keeps every existing MLB/WNBA/NFL route unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V25_CFB_STEP3_2026-09-08T08:00Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v25 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V25_CFB_STEP3_2026-09-08T08:00Z"


render_app()
