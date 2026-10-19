"""Additive Universal Runtime V5 terminal overlay for CFB Over/Under V41.

The frozen Universal Runtime V5 remains the single render owner. This overlay only
advances its destination-loader bindings to V19, which overrides exact CFB /
Over-Under and delegates every other route through V18 unchanged.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_universal_runtime_v5 as prior
from universal_runtime_v5_loader_v19 import choose_prefetch, load_destination, resolve_destination

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • CFB O/U SLIDER + READABILITY V3 OVERLAY"
FROZEN_RUNTIME = "streamlit_memory_lazy_router_universal_runtime_v5"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

prior.choose_prefetch = choose_prefetch
prior.load_destination = load_destination
prior.resolve_destination = resolve_destination

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
