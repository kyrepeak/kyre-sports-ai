"""Kyre Sports AI Streamlit entrypoint — CFB O/U logo recursion hotfix V3.

Router V42 preserves the permanently frozen Router V41/V40/... chain.

Additive hotfix V3:
- preserves original CFB Steps 1-12,
- preserves O/U Upgrade Steps 1-3,
- preserves ESPN logo resolver V1 and logo hotfix V2,
- fixes the runtime RecursionError by calling an immutable capture of the
  certified Step-1 enhanced hero instead of a mutable nested-wrapper symbol,
- keeps all projection, probability, selection, ranking, reliability,
  sportsbook, EV, and simulation behavior unchanged.

Deployment heartbeat: STREAMLIT_MAIN_V42_CFB_OU_LOGO_RECURSION_HOTFIX_V3_2026-09-08T21:33Z.
"""
from __future__ import annotations

from streamlit_memory_lazy_router_v42 import render_app


DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V42_CFB_OU_LOGO_RECURSION_HOTFIX_V3_2026-09-08T21:33Z"


render_app()
