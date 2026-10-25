"""Runtime V5 loader V23 — NFL Spread visual hierarchy V10 compatibility override."""
from __future__ import annotations

import universal_runtime_v5_loader as base_loader
import universal_runtime_v5_loader_v22 as prior
from universal_runtime_v5_loader import DestinationAdapter, choose_prefetch, load_destination, run_prefetch
from universal_runtime_v5_state import RuntimeRoute

MODEL_VERSION = "MONSTER UNIVERSAL RUNTIME V5 LOADER V23 • NFL SPREAD VISUAL HIERARCHY V10"


def resolve_destination(route: RuntimeRoute):
    if route.sport_id == "nfl" and route.market_id == "spread":
        return base_loader.resolve_destination(route)
    return prior.resolve_destination(route)


__all__ = ["MODEL_VERSION", "choose_prefetch", "load_destination", "resolve_destination", "run_prefetch", "DestinationAdapter"]
