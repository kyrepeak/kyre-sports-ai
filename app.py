"""Kyre Sports AI Streamlit entrypoint — CFB O/U Upgrade Step 5 explosive-play engine.

Router V45 preserves the permanently frozen Router V44/V43/... chain.

Additive Upgrade Step 5:
- preserves original CFB Steps 1-12,
- preserves O/U Upgrade Steps 1-4,
- preserves multi-source logo hotfixes V1-V4,
- adds first-party NCAA pass Y/A and pass Y/C explosive-efficiency proxies,
- adds NCAA rush Y/carry and opponent allowed-rate suppression context,
- normalizes FBS/FCS evidence inside each team's own division,
- allows mixed FBS/FCS games without comparing rank pools,
- shrinks early-season explosive signals,
- applies bounded per-team explosive adjustments before unchanged Step-9 rules,
- keeps true 20+ pass / 10+ rush rates fail-closed rather than invented,
- keeps analysis-line explosive/projection weight at 0%,
- adds no sportsbook input, market probability, EV, or Monte Carlo.

Deployment heartbeat: STREAMLIT_MAIN_V45_CFB_OU_UPGRADE_STEP5_EXPLOSIVE_2026-09-08T22:48Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v45 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V45_CFB_OU_UPGRADE_STEP5_EXPLOSIVE_2026-09-08T22:48Z"


render_app()
