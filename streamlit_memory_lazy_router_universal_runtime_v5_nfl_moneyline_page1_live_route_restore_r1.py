"""Terminal successor restoring the certified simple NFL Moneyline Page 1 live.

This overlay gives NFL Moneyline a fresh module identity for long-lived Streamlit
processes while delegating every other route to the current terminal runtime.
It changes route ownership only; Moneyline projection/model behavior remains frozen.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page2_route_restore_v1 as prior
import universal_runtime_v5_loader as canonical_loader
from universal_page_experience_runtime_v5 import render_page_experience_app_v5

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • NFL MONEYLINE PAGE1 SIMPLE LIVE ROUTE RESTORE R1"
FROZEN_RUNTIME = prior.FROZEN_RUNTIME
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

frozen_runtime = prior.frozen_runtime


def resolve_destination(route):
    """Shadow terminal NFL routes that require fresh canonical-loader ownership."""
    if route.sport_id == "nfl" and route.market_id == "game-total":
        return canonical_loader.resolve_destination(route)
    if route.sport_id == "nfl" and route.market_id == "moneyline":
        return canonical_loader._nfl_adapter(route, "nfl_moneyline_hub_v20", ttl_ms=20_000)
    return prior.resolve_destination(route)


frozen_runtime.resolve_destination = resolve_destination
record_bootstrap_import_ms = prior.record_bootstrap_import_ms


def render_app():
    return render_page_experience_app_v5(frozen_runtime)


__all__ = [
    "FROZEN_RUNTIME",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "record_bootstrap_import_ms",
    "render_app",
    "resolve_destination",
]
