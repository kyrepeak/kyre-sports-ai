"""Kyre Sports AI Streamlit entrypoint — CFB O/U Upgrade Step 8 turnover volatility.

Router V48 preserves the permanently frozen Router V47/V46/... chain.

Additive Upgrade Step 8:
- preserves original CFB Steps 1-12,
- preserves O/U Upgrade Steps 1-7,
- preserves multi-source logo hotfixes V1-V4,
- adds direct NCAA turnovers gained/lost and margin evidence,
- parses tied NCAA rows safely even when Rank is blank,
- models offense giveaways vs opponent takeaways,
- normalizes both sides inside FBS/FCS baselines,
- supports mixed FBS/FCS games without cross-division rank comparisons,
- shrinks early-season turnover signals by verified game sample,
- adjusts structural uncertainty only,
- preserves Step-7 projected team points and projected total exactly,
- does not fabricate field-position point value,
- keeps analysis-line turnover/projection weight at 0%,
- adds no sportsbook input, market probability, EV, or Monte Carlo.

Deployment heartbeat: STREAMLIT_MAIN_V48_CFB_OU_UPGRADE_STEP8_TURNOVER_2026-09-09T00:31Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v48 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V48_CFB_OU_UPGRADE_STEP8_TURNOVER_2026-09-09T00:31Z"


render_app()
