"""Kyre Sports AI Streamlit entrypoint — CFB O/U Upgrade Step 3.

Router V39 preserves the permanently frozen Router V38/V37/.../V2 chain down
to the streamlit_memory_lazy_router_v1 bootstrap.

Additive Over/Under Intelligence V2 Step 3 change:
- preserves permanently frozen CFB Steps 1-12,
- preserves permanently frozen O/U Upgrade Steps 1-2,
- preserves College Football Moneyline Step 6 unchanged,
- preserves College Football Game Total Step 12 unchanged,
- keeps the frozen Step-9 qualification/ranking rules unchanged,
- activates a bounded offense-vs-defense matchup adjustment before Step-9 synthesis,
- compares scoring, total yards, passing, rushing, third down, red zone,
  sack pressure, and turnover pressure,
- requires minimum evidence coverage and refuses mixed FBS/FCS rank-pool adjustments,
- caps incremental adjustment at +/-3.5 projected points per team,
- keeps the analysis line at exactly 0% matchup/projection weight,
- does not add sportsbook price, market probability, EV, or Monte Carlo,
- keeps MLB, WNBA, and NFL unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V39_CFB_OU_UPGRADE_STEP3_2026-09-08T20:23Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v39 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V39_CFB_OU_UPGRADE_STEP3_2026-09-08T20:23Z"


render_app()
