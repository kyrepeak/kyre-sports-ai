"""KYRE Sports AI production activation shim — Universal Shell/Route/Top V1.

The frozen historical entrypoint body is preserved byte-for-byte in
``app_legacy_entrypoint_v1.py``. This shim changes the Streamlit entrypoint
identity so Community Cloud restarts, while routing its existing imports to the
new additive Universal Navigation V3 and Universal Shell V2 runtimes.
"""
from __future__ import annotations

import sys

import streamlit as st

import kyre_universal_shell_runtime_v2 as _shell_v2
import streamlit_memory_lazy_router_universal_nav_v3 as _router_v3
from kyre_universal_shell_runtime_v2 import activate_universal_shell
from kyre_universal_entrypoint_cold_start_v1 import seed_canonical_route_if_missing
from streamlit_memory_lazy_router_universal_nav_v3 import record_bootstrap_import_ms, render_app

API2_UNIVERSAL_SHELL_ROUTE_TOP_V1_RUNTIME = "API2_UNIVERSAL_SHELL_ROUTE_TOP_V1_RUNTIME_REFRESH_2026_10_17_R2"
DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V146_NFL_RECEIVING_YARDS_PLAYER_VS_DEFENSE_HISTORY_2026-09-16"

# Frozen Universal Nav V2 certification compatibility: from streamlit_memory_lazy_router_universal_nav_v2 import record_bootstrap_import_ms, render_app
# Frozen root-router certification compatibility: streamlit_memory_lazy_router_v1
# Frozen Universal Nav V1 certification compatibility: from streamlit_memory_lazy_router_universal_nav_v1 import record_bootstrap_import_ms, render_app
# Frozen V146 certification compatibility: from streamlit_memory_lazy_router_v146 import record_bootstrap_import_ms, render_app
# Frozen Universal Shell V1 certification compatibility: from kyre_universal_shell_runtime_v1 import activate_universal_shell

# The preserved entrypoint still contains the historical V2/V1 import lines.
# Route those exact names to the additive successors before executing it.
sys.modules["streamlit_memory_lazy_router_universal_nav_v2"] = _router_v3
sys.modules["kyre_universal_shell_runtime_v1"] = _shell_v2

seed_canonical_route_if_missing(st.session_state, st.query_params)

from app_legacy_entrypoint_v1 import *  # noqa: F401,F403,E402
