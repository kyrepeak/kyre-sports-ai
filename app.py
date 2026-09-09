"""Kyre Sports AI Streamlit entrypoint — CFB O/U Upgrade Step 7 third-down engine.

Router V47 preserves the permanently frozen Router V46/V45/... chain.

Additive Upgrade Step 7:
- preserves original CFB Steps 1-12,
- preserves O/U Upgrade Steps 1-6,
- preserves multi-source logo hotfixes V1-V4,
- adds direct NCAA third-down attempts and conversions,
- parses tied NCAA rows safely even when Rank is blank,
- models offense third-down conversion vs opponent third-down defense,
- normalizes both sides inside FBS/FCS baselines,
- supports mixed FBS/FCS games without cross-division rank comparisons,
- shrinks early-season third-down signals by verified attempt count,
- applies bounded per-team drive-sustain adjustments before unchanged Step-9 rules,
- keeps analysis-line third-down/projection weight at 0%,
- adds no sportsbook input, market probability, EV, or Monte Carlo.

Deployment heartbeat: STREAMLIT_MAIN_V47_CFB_OU_UPGRADE_STEP7_THIRD_DOWN_2026-09-09T00:12Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v47 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V47_CFB_OU_UPGRADE_STEP7_THIRD_DOWN_2026-09-09T00:12Z"


render_app()
