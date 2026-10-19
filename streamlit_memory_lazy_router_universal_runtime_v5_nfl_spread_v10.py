"""Additive Universal Runtime V5 terminal overlay for NFL Spread V10."""
from __future__ import annotations

import streamlit_memory_lazy_router_universal_runtime_v5 as runtime
import streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v6 as prior
from universal_runtime_v5_loader_v23 import choose_prefetch, load_destination, resolve_destination

MODEL_VERSION = "MONSTER UNIVERSAL RUNTIME V5 • NFL SPREAD VISUAL HIERARCHY V10 OVERLAY"
FROZEN_RUNTIME = "streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v6"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

runtime.choose_prefetch = choose_prefetch
runtime.load_destination = load_destination
runtime.resolve_destination = resolve_destination

record_bootstrap_import_ms = prior.record_bootstrap_import_ms


def render_app():
    return prior.render_app()


__all__ = [
    "FROZEN_RUNTIME",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
