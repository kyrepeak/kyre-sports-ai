"""Kyre Sports AI Streamlit entrypoint — CFB O/U Upgrade Step 9 environment.

Router V49 preserves the permanently frozen Router V48/V47/... chain.

Additive Upgrade Step 9:
- preserves original CFB Steps 1-12,
- preserves O/U Upgrade Steps 1-8,
- preserves multi-source logo hotfixes V1-V4,
- resolves exact same-date ESPN event identity even when NCAA lacks ESPN ID,
- adds venue and game-time weather context,
- adds timestamped roster availability auditing,
- refuses to treat empty roster injury flags as proof of health,
- gives injury/availability exactly 0% model weight until reporting completeness is certified,
- uses severe weather only to widen structural uncertainty,
- preserves Step-8 projected team points and projected total exactly,
- keeps analysis-line environment/projection weight at 0%,
- adds no sportsbook input, market probability, EV, or Monte Carlo.

Deployment heartbeat: STREAMLIT_MAIN_V49_CFB_OU_UPGRADE_STEP9_ENVIRONMENT_2026-09-09T00:58Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v49 import render_app

DEPLOYMENT_HEARTBEAT="STREAMLIT_MAIN_V49_CFB_OU_UPGRADE_STEP9_ENVIRONMENT_2026-09-09T00:58Z"

render_app()
