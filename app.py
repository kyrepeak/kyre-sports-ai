"""Kyre Sports AI Streamlit entrypoint — CFB O/U post-12 data recovery.

Router V53 preserves the permanently frozen 12/12 Over/Under stack through
Router V52 and adds a provider-recovery layer above it.

Hotfix behavior:
- ESPN exact event remains primary.
- ESPN visual/team directory can recover stable team IDs.
- Exact team-schedule pair/date matching can recover an ESPN event ID.
- Recovered event IDs unlock ESPN summary weather/venue/rosters.
- Winsipedia supplies all-time game-by-game H2H when ESPN history is missing.
- Partial verified data is displayed instead of a blank gated panel.
- Frozen Step-9/10/11 weighting rules, Step-12 certification, sportsbook/EV
  firewalls, and all 12 permanent freeze contracts remain unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V53_CFB_OU_POST12_DATA_RECOVERY_2026-09-09T03:18Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v53 import render_app

DEPLOYMENT_HEARTBEAT="STREAMLIT_MAIN_V53_CFB_OU_POST12_DATA_RECOVERY_2026-09-09T03:18Z"

render_app()
