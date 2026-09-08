"""Kyre Sports AI Streamlit entrypoint — CFB O/U Upgrade Step 2.

Router V38 preserves the permanently frozen Router V37/V36/.../V2 chain down
to the streamlit_memory_lazy_router_v1 bootstrap.

Additive Over/Under Intelligence V2 Step 2 change:
- preserves permanently frozen CFB Steps 1-12,
- preserves permanently frozen O/U Upgrade Step 1 team logos + matchup header,
- preserves College Football Moneyline Step 6 unchanged,
- preserves College Football Game Total Step 12 unchanged,
- preserves frozen College Football Over/Under Step 8 projection and Step 9 final logic,
- adds display-only AP / Coaches / CFP ranking context,
- adds official NCAA scoring/total/pass/rush offense and defense category ranks,
- adds conference, overall record, home/road splits, and recent form context,
- keeps all Step-2 ranking/record evidence at 0% model/projection/selection weight,
- keeps MLB, WNBA, and NFL unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V38_CFB_OU_UPGRADE_STEP2_2026-09-08T20:04Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v38 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V38_CFB_OU_UPGRADE_STEP2_2026-09-08T20:04Z"


render_app()
