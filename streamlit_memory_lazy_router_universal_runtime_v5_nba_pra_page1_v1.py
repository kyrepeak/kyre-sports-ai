"""Terminal overlay for NBA PRA Page 1 over frozen NFL Daily Picks V4."""
from __future__ import annotations
import streamlit_memory_lazy_router_universal_runtime_v5 as frozen_runtime
import nba_pra_nav_overlay_v1 as nav_overlay
import streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4 as prior
from universal_runtime_v5_loader_nba_pra_page1_v1 import choose_prefetch, load_destination, resolve_destination
MODEL_VERSION="API2 UNIVERSAL RUNTIME V5 • NBA PRA PAGE1 V1 TERMINAL"
FROZEN_RUNTIME="streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4"
MAY_MODIFY_PROJECTION=False
SPORTSBOOK_PROJECTION_INFLUENCE=0.0
nav_overlay.activate()
frozen_runtime.choose_prefetch=choose_prefetch; frozen_runtime.load_destination=load_destination; frozen_runtime.resolve_destination=resolve_destination
record_bootstrap_import_ms=prior.record_bootstrap_import_ms
def render_app(): return prior.render_app()
