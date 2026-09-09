"""Kyre Sports AI Streamlit entrypoint — CFB O/U Upgrade Step 11 form strength.

Router V51 preserves the permanently frozen Router V50/V49/... chain.

Additive Upgrade Step 11:
- preserves original CFB Steps 1-12,
- preserves O/U Upgrade Steps 1-10,
- preserves all multi-source logo hotfixes,
- uses only completed current-season games before kickoff,
- normalizes recent scoring form using verified opponent records,
- shrinks influence by sample size and opponent-record coverage,
- requires at least two current-season games and 60% opponent-record coverage,
- keeps previous-season history at 0% projection weight,
- caps adjustment at ±1.25 points per team and ±2.00 total,
- keeps structural sigma, reliability, feature coverage, and frozen final
  qualification thresholds unchanged,
- keeps analysis-line form weight and direct selection form weight at 0%,
- adds no sportsbook input, market probability, EV, price, or Monte Carlo.

Deployment heartbeat: STREAMLIT_MAIN_V51_CFB_OU_UPGRADE_STEP11_FORM_STRENGTH_2026-09-09T02:10Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v51 import render_app

DEPLOYMENT_HEARTBEAT="STREAMLIT_MAIN_V51_CFB_OU_UPGRADE_STEP11_FORM_STRENGTH_2026-09-09T02:10Z"

render_app()
