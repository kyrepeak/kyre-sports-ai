"""Kyre Sports AI Streamlit entrypoint — CFB mixed-division hotfix.

Router V28 preserves the frozen Router V27/V26/V25/.../V2 chain down to the
`streamlit_memory_lazy_router_v1` bootstrap.

Additive correctness hotfix:
- preserves permanently frozen CFB Steps 1–5,
- advances only College Football -> Moneyline to the mixed-division
  schedule/team-data supplement,
- restores omitted FBS-vs-FCS crossover games when NCAA FBS division-only
  schedule filtering would otherwise return an incomplete slate,
- keeps frozen Moneyline Model V1 probability math unchanged,
- keeps Over/Under, Game Total, MLB, WNBA, and NFL unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V28_CFB_MIXED_DIVISION_2026-09-08T14:48Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v28 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V28_CFB_MIXED_DIVISION_2026-09-08T14:48Z"


render_app()
