"""Kyre Sports AI Streamlit entrypoint — CFB O/U readable Step 8 turnover volatility live.

Router V65 keeps Router V64 / Clean Page V24 untouched and activates additive
Clean Page V25 for College Football Over/Under only.

Clean Page V25 preserves readable Steps 4-7, certified Market Adapter V2
freshness + exact official ESPN event-ID attachment, and Step 5C market
intelligence at 0.0% projection influence. It changes only Step 8 presentation,
translating the already-frozen direct NCAA turnover-volatility engine output into
readable football context. Step 8 may adjust structural uncertainty only; it
cannot move the frozen projected total. No fuzzy matching. No synthetic IDs.
Frozen Schedule V5 and Steps 3-12 projection math remain unchanged.

Deployment heartbeat:
STREAMLIT_MAIN_V65_CFB_OU_READABLE_STEP8_2026-09-10T20:04Z.
"""
from __future__ import annotations

# Retain explicit frozen predecessor imports so the permanent DevSystem guard
# continues proving the older active contracts while V65 is the additive top layer.
from streamlit_memory_lazy_router_v63 import render_app as _frozen_v63_render_app
from streamlit_memory_lazy_router_v64 import render_app as _frozen_v64_render_app
from streamlit_memory_lazy_router_v65 import render_app

DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V65_CFB_OU_READABLE_STEP8_2026-09-10T20:04Z"

render_app()
