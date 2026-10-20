"""Workstream-isolated Universal Runtime V5 overlay for NBA Spread S-tier V2.

This module deliberately owns a unique path so parallel workstreams may advance
shared numbered loaders independently. At import time it adopts the strongest
available upstream base (V25 when present, otherwise V24) and overrides only
the NBA spread destination with Page V9. Every other route delegates unchanged
to the selected base loader.
"""
from __future__ import annotations

import importlib
import importlib.util

from universal_runtime_v5_loader import (
    DestinationAdapter,
    choose_prefetch,
    load_destination,
    run_prefetch,
)
from universal_runtime_v5_state import RuntimeRoute

_BASE_CANDIDATES = (
    "universal_runtime_v5_loader_v25",
    "universal_runtime_v5_loader_v24",
)


def _select_base_loader():
    for name in _BASE_CANDIDATES:
        if importlib.util.find_spec(name) is not None:
            return name, importlib.import_module(name)
    raise ImportError("NBA_SPREAD_STIER_V2_BASE_RUNTIME_UNAVAILABLE")


BASE_LOADER_NAME, _base = _select_base_loader()
MODEL_VERSION = (
    "API2 UNIVERSAL RUNTIME V5 • NBA SPREAD PAGE1 S-TIER V2 • "
    f"BASE={BASE_LOADER_NAME}"
)
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


def resolve_destination(route: RuntimeRoute):
    if route.sport_id == "nba" and route.market_id == "spread":
        base_destination = _base.resolve_destination(route)

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

        return DestinationAdapter(
            base_destination.route_key,
            loader,
            renderer,
            MODEL_VERSION,
            base_destination.ttl_ms,
        )
    return _base.resolve_destination(route)


__all__ = [
    "BASE_LOADER_NAME",
    "DestinationAdapter",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "choose_prefetch",
    "load_destination",
    "resolve_destination",
    "run_prefetch",
]
