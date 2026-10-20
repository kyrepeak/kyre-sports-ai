"""Terminal runtime overlay for NFL Daily Picks Command Center V3.

Preserves the current NBA Spread S-tier terminal and all unrelated routes while
injecting only the isolated NFL Daily Picks V3 runtime owner. Rendering is
handed to Universal Atomic Navigation V1 so every selected destination replaces
the outgoing destination atomically without background destination prefetch.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_universal_runtime_v5 as frozen_runtime
import streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v8 as prior
from universal_atomic_navigation_runtime_v1 import render_atomic_app
from universal_runtime_v5_loader_nfl_daily_picks_command_v3 import (
    choose_prefetch,
    load_destination,
    resolve_destination,
)

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • NFL DAILY PICKS COMMAND CENTER V3 TERMINAL • ATOMIC NAV V1"
FROZEN_RUNTIME = "streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v8"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

frozen_runtime.choose_prefetch = choose_prefetch
frozen_runtime.load_destination = load_destination
frozen_runtime.resolve_destination = resolve_destination

record_bootstrap_import_ms = prior.record_bootstrap_import_ms


def render_app():
    return render_atomic_app(frozen_runtime)


__all__ = [
    "FROZEN_RUNTIME",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
