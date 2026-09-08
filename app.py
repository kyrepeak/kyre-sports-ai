"""Kyre Sports AI Streamlit entrypoint — CFB O/U ESPN logo hotfix V2.

Router V41 preserves the permanently frozen Router V40/V39/... chain.

Additive hotfix V2:
- preserves original CFB Steps 1-12,
- preserves O/U Upgrade Steps 1-3,
- preserves the V1 ESPN resolver,
- fixes the runtime wrapper path by forcing logo resolution inside the active
  Step-3 hero call instead of relying on an outer patch through nested wrappers,
- keeps all projection, probability, selection, ranking, reliability,
  sportsbook, EV, and simulation behavior unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V41_CFB_OU_ESPN_LOGO_HOTFIX_V2_2026-09-08T21:00Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v41 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V41_CFB_OU_ESPN_LOGO_HOTFIX_V2_2026-09-08T21:00Z"


render_app()
