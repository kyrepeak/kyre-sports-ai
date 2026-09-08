"""Kyre Sports AI Streamlit entrypoint — CFB full FBS slate fallback.

Router V29 preserves the frozen Router V28/V27/V26/.../V2 chain down to the
`streamlit_memory_lazy_router_v1` bootstrap.

Additive correctness hotfix:
- preserves permanently frozen CFB Steps 1–5,
- preserves the frozen mixed-division Router V28 correctness layer,
- advances only College Football -> Moneyline to the full FBS slate fallback,
- admits only unscoped ESPN events containing at least one verified FBS
  team-directory member,
- keeps frozen Moneyline Model V1 probability math unchanged,
- keeps Over/Under, Game Total, MLB, WNBA, and NFL unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V29_CFB_FULL_FBS_SLATE_2026-09-08T15:50Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v29 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V29_CFB_FULL_FBS_SLATE_2026-09-08T15:50Z"


render_app()
