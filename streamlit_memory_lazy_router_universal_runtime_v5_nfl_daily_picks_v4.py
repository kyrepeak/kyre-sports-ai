"""Terminal runtime overlay for NFL Daily Picks Premium Smart Live V4."""
from __future__ import annotations

import streamlit_memory_lazy_router_universal_runtime_v5 as frozen_runtime
import streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3 as prior
from universal_runtime_v5_loader_nfl_daily_picks_command_v4 import choose_prefetch, load_destination, resolve_destination

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • NFL DAILY PICKS PREMIUM SMART LIVE V4 TERMINAL"
FROZEN_RUNTIME = "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

frozen_runtime.choose_prefetch = choose_prefetch
frozen_runtime.load_destination = load_destination
frozen_runtime.resolve_destination = resolve_destination

record_bootstrap_import_ms = prior.record_bootstrap_import_ms


def render_app():
    return prior.render_app()


__all__ = ["FROZEN_RUNTIME", "MAY_MODIFY_PROJECTION", "MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE", "record_bootstrap_import_ms", "render_app"]
