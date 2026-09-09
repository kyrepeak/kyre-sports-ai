"""Kyre Sports AI Streamlit entrypoint — CFB O/U Upgrade Step 10 history.

Router V50 preserves the permanently frozen Router V49/V48/... chain.

Additive Upgrade Step 10:
- preserves original CFB Steps 1-12,
- preserves O/U Upgrade Steps 1-9,
- preserves all multi-source logo hotfixes,
- gathers completed pre-kickoff ESPN team scoring history,
- resolves true head-to-head meetings using exact ESPN team IDs,
- excludes future events and the target event from historical samples,
- displays last-eight scoring/allowing/combined-total context,
- keeps historical roster continuity and opponent-strength adjustment uncertified,
- gives history exactly 0% projection, selection, and analysis-line weight,
- preserves Step-9 projected team points, projected total, sigma, reliability,
  probabilities, and frozen qualification rules exactly,
- adds no sportsbook input, market probability, EV, price, or Monte Carlo.

Deployment heartbeat: STREAMLIT_MAIN_V50_CFB_OU_UPGRADE_STEP10_HISTORY_2026-09-09T01:50Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v50 import render_app

DEPLOYMENT_HEARTBEAT="STREAMLIT_MAIN_V50_CFB_OU_UPGRADE_STEP10_HISTORY_2026-09-09T01:50Z"

render_app()
