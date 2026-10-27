"""KYRE Sports AI production entrypoint — sitewide HTML render compatibility R2."""
from time import perf_counter

import importlib
import sys

import streamlit as st

from streamlit_html_compat_v1 import install_sitewide_html_compat
from nba_pra_page2_role_runtime_v4 import install as install_nba_pra_page2_role_runtime_v4

_STREAMLIT_DEPLOYMENT_HEARTBEAT = "api2-universal-loading-progress-v1-production-repair-r1-20261022"
_STEP2G_DEPLOYMENT_MARKER = "API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1"
_NFL_GAME_TOTAL_DENSITY_DEPLOYMENT_HEARTBEAT = "API2_NFL_GAME_TOTAL_PAGE1_MOBILE_DENSITY_R1_20261026"
_NFL_GAME_TOTAL_CACHE_BUST_DEPLOYMENT_HEARTBEAT = "API2_NFL_GAME_TOTAL_PAGE1_MODULE_CACHE_BUST_R1_20261026"
_NFL_GAME_TOTAL_PAGE2_STIER_CACHE_BUST_HEARTBEAT = "API2_NFL_GAME_TOTAL_PAGE2_STIER_CACHE_BUST_R1_20261027"
_NFL_MONEYLINE_PAGE2_ROUTE_RESTORE_HEARTBEAT = "API2_NFL_MONEYLINE_PAGE2_WAR_ROOM_ROUTE_RESTORE_R1_20261026"
_NFL_MONEYLINE_PAGE1_SIMPLE_LIVE_ROUTE_RESTORE_HEARTBEAT = "API2_NFL_MONEYLINE_PAGE1_SIMPLE_LIVE_ROUTE_RESTORE_R1_20261026"
_NFL_MONEYLINE_PAGE1_CURRENT_CONVERGENCE_HEARTBEAT = "API2_NFL_MONEYLINE_PAGE1_CURRENT_CONVERGENCE_R1_20261026"
_API2_SITEWIDE_RENDER_REPAIR_HEARTBEAT = "API2_SITEWIDE_RENDER_REPAIR_R1_20261026"
_API2_SITEWIDE_DEPLOYMENT_CONVERGENCE_R2_HEARTBEAT = "API2_SITEWIDE_RENDER_DEPLOYMENT_CONVERGENCE_R2_20261026"
_API2_SITEWIDE_HTML_RENDER_COMPAT_R2_HEARTBEAT = "API2_SITEWIDE_HTML_RENDER_COMPAT_R2_20261026"
_BOOTSTRAP_STARTED = perf_counter()

# Install before any presentation heartbeat or lazily imported page renders. The
# wrappers are stateless/idempotent presentation successors only.
install_sitewide_html_compat(st)
install_nba_pra_page2_role_runtime_v4()

# These pages are lazily imported by Universal Runtime V5. Streamlit can keep a
# prior module object alive across source-only deploys. Evict only the exact page
# and route-owner modules whose source identity changed; canonical route identity
# and frozen Page 1 ancestry are preserved.
sys.modules.pop("universal_runtime_v5_loader", None)
sys.modules.pop("streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page1_live_route_restore_r1", None)
sys.modules.pop("nfl_game_totals_hub_v12", None)
sys.modules.pop("nfl_game_totals_page1_s_tier_v1", None)
sys.modules.pop("nfl_moneyline_hub_v20", None)
sys.modules.pop("nba_pra_runtime_v2", None)
sys.modules.pop("nba_pra_page2_sync_v1", None)
sys.modules.pop("nba_pra_page2_command_center_v4", None)
importlib.invalidate_caches()

# Frozen ancestry markers retained for regression/documentation only:
# streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1
# streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_page2_v3
# streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_v1
# streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_repair_v1
# streamlit_memory_lazy_router_universal_runtime_v5_loading_progress_v1
# streamlit_memory_lazy_router_universal_runtime_v5_loading_progress_repair_r1
# streamlit_memory_lazy_router_universal_runtime_v5_cfb_game_total_bootstrap_repair_r1
# streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1
# streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page2_route_restore_v1
from streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page1_live_route_restore_r1 import (  # noqa: E402
    record_bootstrap_import_ms,
    render_app,
)
from devsystem.monster_runtime_identity_v1 import emit_runtime_identity_marker  # noqa: E402

# Off-screen but browser-visible production identity markers for Step 2G proof.
# The compatibility shim routes this pure HTML payload through st.html so the
# R2 marker itself proves the repaired HTML path is active in production.
st.markdown(
    f'<span style="position:absolute;left:-10000px;top:auto;width:1px;height:1px;overflow:hidden">{_STEP2G_DEPLOYMENT_MARKER} {_NFL_GAME_TOTAL_DENSITY_DEPLOYMENT_HEARTBEAT} {_NFL_GAME_TOTAL_CACHE_BUST_DEPLOYMENT_HEARTBEAT} {_NFL_GAME_TOTAL_PAGE2_STIER_CACHE_BUST_HEARTBEAT} {_NFL_MONEYLINE_PAGE2_ROUTE_RESTORE_HEARTBEAT} {_NFL_MONEYLINE_PAGE1_SIMPLE_LIVE_ROUTE_RESTORE_HEARTBEAT} {_NFL_MONEYLINE_PAGE1_CURRENT_CONVERGENCE_HEARTBEAT} {_API2_SITEWIDE_RENDER_REPAIR_HEARTBEAT} {_API2_SITEWIDE_DEPLOYMENT_CONVERGENCE_R2_HEARTBEAT} {_API2_SITEWIDE_HTML_RENDER_COMPAT_R2_HEARTBEAT}</span>',
    unsafe_allow_html=True,
)

record_bootstrap_import_ms((perf_counter() - _BOOTSTRAP_STARTED) * 1000.0)
render_app()
emit_runtime_identity_marker()