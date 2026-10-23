"""Terminal overlay for universal same-tab navigation + maximum-speed runtime V1.

The terminal keeps the current NBA PRA resolver lineage, preserves the frozen
CFB Top Picks V19 destination directly, and renders through Universal Page
Experience Runtime V2. No sports model/provider logic is changed.
"""
from __future__ import annotations

import importlib

import streamlit_memory_lazy_router_universal_runtime_v5 as frozen_runtime
import streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1 as prior
from universal_page_experience_runtime_v2 import render_page_experience_app_v2
from universal_runtime_v5_loader import DestinationAdapter

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • STREAMLIT NAVIGATION SPEED V1"
FROZEN_RUNTIME = "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_prior_resolve_destination = prior.resolve_destination


def resolve_destination(route):
    """Preserve current route ownership while collapsing the CFB overlay imports."""
    if route.sport_id == "cfb" and route.market_id == "top-picks":
        base = _prior_resolve_destination(route)
        return DestinationAdapter(
            base.route_key,
            lambda: importlib.import_module("cfb_top_picks_page_v19"),
            lambda page: page.render_cfb_hub("Top Picks"),
            "cfb_top_picks_page_v19",
            30_000,
        )
    return _prior_resolve_destination(route)


frozen_runtime.resolve_destination = resolve_destination
record_bootstrap_import_ms = prior.record_bootstrap_import_ms


def render_app():
    return render_page_experience_app_v2(frozen_runtime)


__all__ = [
    "FROZEN_RUNTIME",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
    "resolve_destination",
]
