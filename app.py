"""Kyre Sports AI Streamlit entrypoint — Hits root-route correction.

Router V22 preserves the frozen Router V21/V20/V19/V18/V17/V16/V15/V14/V13/V12/V11/V10/V9/V8/V7/V6/V5/V4/V3/V2
chain down to the `streamlit_memory_lazy_router_v1` bootstrap.

Critical routing correction:
- Router V3 is the first wrapper that directly intercepts MLB 1+ Hit.
- V22 patches that exact root Hits boundary so current Hits UI V13.21 is
  reachable in production.
- Moneyline, Matchup Explorer, and every non-Hits route keep delegating through
  the frozen chain unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V22_2026-09-08T06:07Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v22 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V22_2026-09-08T06:07Z"


render_app()
