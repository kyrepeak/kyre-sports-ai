"""Runtime V5 loader V25 — NBA Spread Page-1 S-tier V2 override."""
from __future__ import annotations

import importlib

import universal_runtime_v5_loader_v24 as prior
from universal_runtime_v5_loader import DestinationAdapter, choose_prefetch, load_destination, run_prefetch
from universal_runtime_v5_state import RuntimeRoute

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 LOADER V25 • NBA SPREAD PAGE1 S-TIER V2"


def resolve_destination(route: RuntimeRoute):
    if route.sport_id == "nba" and route.market_id == "spread":
        base = prior.resolve_destination(route)

        def loader():
            return (
                importlib.import_module("nba_spread_page_v9"),
                importlib.import_module("nba_spread_page_provider_resilience_step3_r1"),
            )

        def renderer(bundle):
            page, provider_bridge = bundle
            bind = getattr(provider_bridge, "_bind_resilient_schedule_loader", None)
            if callable(bind):
                bind()
            return page.render_nba_spread_page()

        return DestinationAdapter(base.route_key, loader, renderer, MODEL_VERSION, base.ttl_ms)
    return prior.resolve_destination(route)


__all__ = ["MODEL_VERSION", "choose_prefetch", "load_destination", "resolve_destination", "run_prefetch", "DestinationAdapter"]
