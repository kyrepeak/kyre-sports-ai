"""Runtime V5 loader V19 — CFB Over/Under Slider + Readability V3 override."""
from __future__ import annotations

import importlib

import universal_runtime_v5_loader_v18 as prior
from universal_runtime_v5_loader import DestinationAdapter, choose_prefetch, load_destination, run_prefetch
from universal_runtime_v5_state import RuntimeRoute

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 LOADER V19 • CFB O/U SLIDER + READABILITY V3"


def resolve_destination(route: RuntimeRoute):
    if route.sport_id == "cfb" and route.market_id == "over-under":
        base = prior.resolve_destination(route)

        def loader():
            return importlib.import_module("cfb_over_under_clean_page_v41")

        def renderer(page):
            return base.renderer(page)

        return DestinationAdapter(base.route_key, loader, renderer, MODEL_VERSION, base.ttl_ms)
    return prior.resolve_destination(route)


__all__ = ["MODEL_VERSION", "choose_prefetch", "load_destination", "resolve_destination", "run_prefetch"]
