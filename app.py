"""Kyre Sports AI Streamlit entrypoint — CFB O/U Upgrade Step 1.

Router V37 preserves the permanently frozen Router V36/V35/.../V2 chain down
to the streamlit_memory_lazy_router_v1 bootstrap.

Additive Over/Under Intelligence V2 Step 1 change:
- preserves permanently frozen CFB Steps 1-12,
- preserves College Football Moneyline Step 6 unchanged,
- preserves College Football Game Total Step 12 unchanged,
- preserves frozen College Football Over/Under Step 8 projection and Step 9 final logic,
- upgrades only the Over/Under matchup presentation with college team logos and a
  compact matchup header for kickoff, stadium, TV, status, and site,
- keeps logo metadata at 0% model/projection/selection weight,
- keeps MLB, WNBA, and NFL unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V37_CFB_OU_UPGRADE_STEP1_2026-09-08T19:46Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v37 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V37_CFB_OU_UPGRADE_STEP1_2026-09-08T19:46Z"


render_app()
