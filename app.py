"""Kyre Sports AI Streamlit entrypoint — CFB O/U Upgrade Step 4 pace.

Router V44 preserves the permanently frozen Router V43/V42/... chain.

Additive Upgrade Step 4:
- preserves original CFB Steps 1-12,
- preserves O/U Upgrade Steps 1-3,
- preserves multi-source logo hotfixes V1-V4,
- adds NCAA offensive plays/game,
- adds NCAA Time of Possession -> seconds/offensive play,
- computes division-aware expected combined plays with early-sample shrinkage,
- applies a bounded pace adjustment before unchanged Step-9 final rules,
- keeps direct possession counts fail-closed instead of inventing drives,
- keeps analysis-line projection/pace weight at 0%,
- adds no sportsbook input, market probability, EV, or Monte Carlo.

Deployment heartbeat: STREAMLIT_MAIN_V44_CFB_OU_UPGRADE_STEP4_PACE_2026-09-08T22:26Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v44 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V44_CFB_OU_UPGRADE_STEP4_PACE_2026-09-08T22:26Z"


render_app()
