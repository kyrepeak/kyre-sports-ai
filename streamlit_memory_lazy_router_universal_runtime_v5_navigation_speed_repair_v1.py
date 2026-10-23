"""Terminal repair for Universal Streamlit Navigation Speed V1 regressions.

Preserves same-tab/latest-tap speed guards while restoring NBA PRA registry
activation order and route-transition loading behavior.
"""
from __future__ import annotations

import importlib

# IMPORTANT: this import must happen before frozen Runtime V5 so the NBA PRA
# overlay activates before universal_sports_nav_ui_v2 snapshots the registry.
import streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1 as prior
import streamlit_memory_lazy_router_universal_runtime_v5 as frozen_runtime
import universal_runtime_v5_loader as canonical_loader
from universal_page_experience_runtime_v3 import render_page_experience_app_v3
from universal_runtime_v5_loader import DestinationAdapter

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • STREAMLIT NAVIGATION SPEED REPAIR V1"
FROZEN_RUNTIME = "streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_v1"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_prior_resolve_destination = prior.resolve_destination


def resolve_destination(route):
    """Preserve prior route ownership and the frozen CFB Top Picks V19 successor."""
    if route.sport_id == "nfl" and route.market_id == "rushing-yards":
        return canonical_loader.resolve_destination(route)
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
    return render_page_experience_app_v3(frozen_runtime)


__all__ = [
    "FROZEN_RUNTIME",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
    "resolve_destination",
]
