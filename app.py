"""Kyre Sports AI Streamlit entrypoint — CFB O/U readable Step 6 red-zone live.

Router V63 keeps Router V62 / Clean Page V22 untouched and activates additive
Clean Page V23 for College Football Over/Under only.

Clean Page V23 preserves readable Steps 4-5, certified Market Adapter V2
freshness + exact official ESPN event-ID attachment, and Step 5C market
intelligence at 0.0% projection influence. It changes only Step 6 presentation,
translating the already-frozen direct NCAA red-zone engine output into readable
football context. No fuzzy matching. No synthetic IDs. Frozen Schedule V5 and
Steps 3-12 projection math remain unchanged.

Deployment heartbeat:
STREAMLIT_MAIN_V63_CFB_OU_READABLE_STEP6_2026-09-10T19:00Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v63 import render_app

DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V63_CFB_OU_READABLE_STEP6_2026-09-10T19:00Z"

render_app()
