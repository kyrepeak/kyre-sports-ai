"""Kyre Sports AI Streamlit entrypoint — CFB NCAA scoreboard hotfix.

Router V29 preserves the frozen Router V28/V27/V26/.../V2 chain down to the
`streamlit_memory_lazy_router_v1` bootstrap.

Additive correctness hotfix:
- preserves permanently frozen CFB Steps 1–5,
- preserves the frozen mixed-division hotfix,
- advances only College Football -> Moneyline to current NCAA date-scoped
  FBS scoreboard completeness,
- keeps frozen Moneyline Model V1 probability math unchanged,
- keeps Over/Under, Game Total, MLB, WNBA, and NFL unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V29_CFB_SCOREBOARD_2026-09-08T15:50Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v29 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V29_CFB_SCOREBOARD_2026-09-08T15:50Z"


render_app()
