"""Kyre Sports AI Streamlit entrypoint — CFB O/U visible-data-path hotfix.

Router V55 preserves the frozen 12/12 stack, frozen post-12 recovery, and
frozen V54 deep-data reconciliation. It fixes the final presentation handoff so
the reconciled game + away + home profiles reach the visible Step-1/Step-2
cards, and uses alias-safe Schedule V4 enrichment for the visible slate.

Deployment heartbeat:
STREAMLIT_MAIN_V55_CFB_OU_VISIBLE_DATA_PATH_2026-09-09T04:28Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v55 import render_app

DEPLOYMENT_HEARTBEAT="STREAMLIT_MAIN_V55_CFB_OU_VISIBLE_DATA_PATH_2026-09-09T04:28Z"

render_app()
