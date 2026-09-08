"""Kyre Sports AI Streamlit entrypoint — CFB O/U multi-source logo hotfix V4.

Router V43 preserves the permanently frozen Router V42/V41/... chain.

Additive hotfix V4:
- preserves original CFB Steps 1-12,
- preserves O/U Upgrade Steps 1-3,
- preserves logo hotfixes V1-V3,
- keeps ESPN as the first logo source,
- fills missing team logos from official athletics websites,
  Wikipedia/Wikimedia page images, and Wikimedia Commons,
- resolves each team independently so one failed provider does not blank both sides,
- keeps all projection, probability, selection, ranking, reliability,
  sportsbook, EV, and simulation behavior unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V43_CFB_OU_MULTISOURCE_LOGO_HOTFIX_V4_2026-09-08T21:51Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v43 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V43_CFB_OU_MULTISOURCE_LOGO_HOTFIX_V4_2026-09-08T21:51Z"


render_app()
