"""Kyre Sports AI Streamlit entrypoint — CFB O/U central runtime team-data hotfix.

Router V56 preserves every frozen Over/Under layer and fixes the first runtime
team-data handoff itself. The base page now consumes reconciled profiles before
any Step-1/Step-2 card renders, with a verified local snapshot fallback when a
Streamlit runtime cannot reach live providers.

Deployment heartbeat:
STREAMLIT_MAIN_V56_CFB_OU_RUNTIME_TEAM_DATA_2026-09-09T05:02Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v56 import render_app

DEPLOYMENT_HEARTBEAT="STREAMLIT_MAIN_V56_CFB_OU_RUNTIME_TEAM_DATA_2026-09-09T05:02Z"

render_app()
