"""Kyre Sports AI Streamlit entrypoint — direct clean CFB Over/Under page.

Router V57 removes the legacy nested Step-1/Step-2 presentation chain from the
active College Football Over/Under route. The page now renders current runtime
data directly, while certified Steps 3-12 model math remains frozen and reused.

Deployment heartbeat:
STREAMLIT_MAIN_V57_CFB_OU_CLEAN_PAGE_2026-09-09T10:25Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v57 import render_app

DEPLOYMENT_HEARTBEAT="STREAMLIT_MAIN_V57_CFB_OU_CLEAN_PAGE_2026-09-09T10:25Z"

render_app()
