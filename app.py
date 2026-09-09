"""Kyre Sports AI Streamlit entrypoint — live CFB Over/Under odds page.

Router V58 keeps the frozen Clean Page V17 baseline untouched and activates the
additive Clean Page V18 market adapter for College Football Over/Under only.

The production CFB odds endpoint auto-fills the current sportsbook game total
as the analysis threshold while all frozen projection formulas remain unchanged
and sportsbook projection weight remains 0%.

Deployment heartbeat:
STREAMLIT_MAIN_V58_CFB_OU_LIVE_ODDS_2026-09-09T22:58Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v58 import render_app

DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V58_CFB_OU_LIVE_ODDS_2026-09-09T22:58Z"

render_app()
