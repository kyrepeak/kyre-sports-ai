"""Successor-only terminal overlay for CFB Top Picks Page 1 cleanup V4."""
from __future__ import annotations

import importlib

import streamlit_memory_lazy_router_universal_runtime_v5 as frozen_runtime
import streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v3 as prior
from universal_runtime_v5_loader import DestinationAdapter

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • CFB TOP PICKS PAGE1 CLEANUP V4 TERMINAL"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_prior_resolve_destination = prior.resolve_destination


def resolve_destination(route):
    if route.sport_id == "cfb" and route.market_id == "top-picks":
        base = _prior_resolve_destination(route)

        def loader():
            return importlib.import_module("cfb_top_picks_page_v15")

        def renderer(page):
            return page.render_cfb_hub("Top Picks")

        return DestinationAdapter(base.route_key, loader, renderer, MODEL_VERSION, 30_000)
    return _prior_resolve_destination(route)


frozen_runtime.resolve_destination = resolve_destination
record_bootstrap_import_ms = prior.record_bootstrap_import_ms
render_app = prior.render_app

__all__ = ["MODEL_VERSION", "record_bootstrap_import_ms", "render_app", "resolve_destination"]
