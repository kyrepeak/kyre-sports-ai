"""Kyre Sports AI Streamlit entrypoint — CFB O/U Step 6 market intelligence live.

Router V60 keeps permanently frozen Router V59 / Clean Page V19 untouched and
activates additive Clean Page V20 for College Football Over/Under only.

Clean Page V20 uses certified Market Adapter V2 for freshness + exact official
ESPN event-ID attachment, then activates certified Step 5C market intelligence
for display/context only. Market data remains 0.0% influence on frozen projection
math. No fuzzy matching. No synthetic IDs. Frozen Schedule V5 and Steps 3-12
projection math remain unchanged.

Deployment heartbeat:
STREAMLIT_MAIN_V60_CFB_OU_MARKET_INTELLIGENCE_2026-09-10T15:00Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v60 import render_app

DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V60_CFB_OU_MARKET_INTELLIGENCE_2026-09-10T15:00Z"

render_app()
