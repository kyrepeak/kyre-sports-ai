"""Kyre Sports AI Streamlit entrypoint — CFB O/U readable Step 7 third-down live.

Router V64 keeps Router V63 / Clean Page V23 untouched and activates additive
Clean Page V24 for College Football Over/Under only.

Clean Page V24 preserves readable Steps 4-6, certified Market Adapter V2
freshness + exact official ESPN event-ID attachment, and Step 5C market
intelligence at 0.0% projection influence. It changes only Step 7 presentation,
translating the already-frozen direct NCAA third-down engine output into readable
football context. No fuzzy matching. No synthetic IDs. Frozen Schedule V5 and
Steps 3-12 projection math remain unchanged.

Deployment heartbeat:
STREAMLIT_MAIN_V64_CFB_OU_READABLE_STEP7_2026-09-10T19:26Z.
"""
from __future__ import annotations

# Import the frozen predecessor explicitly so the existing permanent DevSystem
# guard continues proving the V63 contract while V64 is the active additive top layer.
from streamlit_memory_lazy_router_v63 import render_app as _frozen_v63_render_app
from streamlit_memory_lazy_router_v64 import render_app

DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V64_CFB_OU_READABLE_STEP7_2026-09-10T19:26Z"

render_app()
