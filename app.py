"""Kyre Sports AI Streamlit entrypoint — CFB O/U deep current-data reconciliation.

Router V54 preserves the complete frozen 12/12 Over/Under stack and frozen
post-12 provider recovery, then adds a current-evidence reconciliation layer.

It repairs stale records, home/road splits, recent form, exact venue/broadcast,
head coach, AP/Coaches/CFP context, and source auditing from verified current
providers before the unchanged frozen model engines run.

Deployment heartbeat:
STREAMLIT_MAIN_V54_CFB_OU_DEEP_DATA_RECONCILIATION_2026-09-09T04:08Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v54 import render_app

DEPLOYMENT_HEARTBEAT="STREAMLIT_MAIN_V54_CFB_OU_DEEP_DATA_RECONCILIATION_2026-09-09T04:08Z"

render_app()
