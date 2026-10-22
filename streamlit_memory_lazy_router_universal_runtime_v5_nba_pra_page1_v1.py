"""Terminal overlay for NBA PRA Page 1 V2 over frozen NFL Daily Picks V4."""
from __future__ import annotations
import importlib
import nba_pra_nav_overlay_v1 as nav_overlay

nav_overlay.activate()

import streamlit_memory_lazy_router_universal_runtime_v5 as frozen_runtime
import streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4 as prior
import universal_runtime_v5_loader as canonical_loader
from universal_runtime_v5_loader import DestinationAdapter
from universal_runtime_v5_loader_nba_pra_page1_v1 import (
    choose_prefetch,
    load_destination,
    resolve_destination as _v1_resolve_destination,
)

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • NBA PRA PAGE2 V1 TERMINAL"
FROZEN_RUNTIME = "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4"
FROZEN_PAGE1_MODULE = "nba_pra_page1_v2"
FROZEN_PAGE1_RENDERER = "render_nba_pra_page1_v2"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def resolve_destination(route):
    if route.sport_id == "nfl" and route.market_id == "passing-yards":
        return canonical_loader.resolve_destination(route)
    if route.sport_id == "nba" and route.market_id == "pra":
        base = _v1_resolve_destination(route)
        def loader():
            return importlib.import_module("nba_pra_runtime_v2")
        def renderer(page):
            return page.render_nba_pra_runtime_v2()
        return DestinationAdapter(base.route_key, loader, renderer, MODEL_VERSION, 30_000)
    return _v1_resolve_destination(route)


frozen_runtime.choose_prefetch = choose_prefetch
frozen_runtime.load_destination = load_destination
frozen_runtime.resolve_destination = resolve_destination
record_bootstrap_import_ms = prior.record_bootstrap_import_ms


def render_app():
    return prior.render_app()
