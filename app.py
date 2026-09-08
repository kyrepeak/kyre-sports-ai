"""Kyre Sports AI Streamlit entrypoint — CFB Step 7 Over/Under Foundation.

Router V31 preserves the permanently frozen Router V30/V29/.../V2 chain down
to the streamlit_memory_lazy_router_v1 bootstrap.

Additive Step 7 change:
- preserves permanently frozen CFB Steps 1-6,
- preserves College Football Moneyline Step 6 unchanged,
- advances only College Football -> Over/Under to its dedicated foundation,
- keeps the Over/Under model/ranking OFF until Steps 8-9,
- keeps Game Total, MLB, WNBA, and NFL unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V31_CFB_STEP7_2026-09-08T17:05Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v31 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V31_CFB_STEP7_2026-09-08T17:05Z"


render_app()
