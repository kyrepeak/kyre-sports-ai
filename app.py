"""Kyre Sports AI Streamlit entrypoint — CFB O/U ESPN logo hotfix.

Router V40 preserves the permanently frozen Router V39/V38/... chain.

Additive hotfix:
- preserves original CFB Steps 1-12,
- preserves O/U Upgrade Steps 1-3,
- changes only presentation-time college team-logo resolution,
- adds safe ESPN alias matching for names such as Miami (FL) / Miami and
  Florida A&M / Florida A&M Rattlers,
- falls back to verified ESPN event summary and ESPN team-id logo CDN,
- keeps all projection, probability, selection, ranking, reliability,
  sportsbook, EV, and simulation behavior unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V40_CFB_OU_ESPN_LOGO_HOTFIX_2026-09-08T20:42Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v40 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V40_CFB_OU_ESPN_LOGO_HOTFIX_2026-09-08T20:42Z"


render_app()
