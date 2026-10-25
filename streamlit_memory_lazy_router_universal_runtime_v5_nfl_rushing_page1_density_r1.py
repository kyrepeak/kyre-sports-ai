"""API2 terminal successor for compact NFL Rushing Yards Page 1 density R1.

Shadows only NFL / Rushing Yards to the presentation-only V2 board. Every other
route delegates to the previously frozen production terminal unchanged.
"""
from __future__ import annotations

import importlib

import streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1 as prior
from universal_page_experience_runtime_v5 import render_page_experience_app_v5
from universal_runtime_v5_loader import DestinationAdapter

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • NFL RUSHING PAGE1 DENSITY R1"
FROZEN_RUNTIME = prior.FROZEN_RUNTIME
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

frozen_runtime = prior.frozen_runtime
_prior_resolve_destination = prior.resolve_destination


def resolve_destination(route):
    """Shadow only NFL Rushing Yards; preserve every unrelated production route."""
    if route.sport_id == "nfl" and route.market_id == "rushing-yards":
        base = _prior_resolve_destination(route)

        def loader():
            return importlib.import_module("nfl_rushing_yards_simple_rb_grid_v2")

        def renderer(page):
            return page.render_nfl_rushing_yards_simple_rb_grid_v2()

        return DestinationAdapter(
            base.route_key,
            loader,
            renderer,
            "nfl_rushing_yards_simple_rb_grid_v2_density_r1",
            base.ttl_ms,
        )
    return _prior_resolve_destination(route)


frozen_runtime.resolve_destination = resolve_destination
record_bootstrap_import_ms = prior.record_bootstrap_import_ms


def render_app():
    return render_page_experience_app_v5(frozen_runtime)


__all__ = [
    "FROZEN_RUNTIME",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
    "resolve_destination",
]
