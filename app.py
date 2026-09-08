"""Kyre Sports AI Streamlit entrypoint — CFB O/U Upgrade Step 6 red-zone engine.

Router V46 preserves the permanently frozen Router V45/V44/... chain.

Additive Upgrade Step 6:
- preserves original CFB Steps 1-12,
- preserves O/U Upgrade Steps 1-5,
- preserves multi-source logo hotfixes V1-V4,
- adds direct NCAA red-zone attempts and outcome rates,
- parses tied NCAA rows safely even when Rank is blank,
- models touchdown conversion and estimated points per red-zone trip,
- normalizes offense and opponent-allowed rates inside FBS/FCS baselines,
- supports mixed FBS/FCS games without cross-division rank comparisons,
- shrinks early-season red-zone signals by verified attempt count,
- applies bounded per-team red-zone adjustments before unchanged Step-9 rules,
- keeps analysis-line red-zone/projection weight at 0%,
- adds no sportsbook input, market probability, EV, or Monte Carlo.

Deployment heartbeat: STREAMLIT_MAIN_V46_CFB_OU_UPGRADE_STEP6_RED_ZONE_2026-09-08T23:16Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v46 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V46_CFB_OU_UPGRADE_STEP6_RED_ZONE_2026-09-08T23:16Z"


render_app()
