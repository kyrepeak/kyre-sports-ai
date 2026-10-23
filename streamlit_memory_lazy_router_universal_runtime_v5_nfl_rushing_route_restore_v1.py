"""Terminal successor restoring canonical NFL Rushing Yards ownership.

This overlay preserves the current CFB Game Total bootstrap terminal and shadows
only NFL / Rushing Yards back to the frozen canonical Kyre Sports API RB board.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_universal_runtime_v5_cfb_game_total_bootstrap_repair_r1 as prior
import universal_runtime_v5_loader as canonical_loader
from universal_page_experience_runtime_v5 import render_page_experience_app_v5

MODEL_VERSION = "API2 UNIVERSAL RUNTIME V5 • NFL RUSHING ROUTE RESTORE V1"
FROZEN_RUNTIME = prior.FROZEN_RUNTIME
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

frozen_runtime = prior.frozen_runtime
_prior_resolve_destination = prior.resolve_destination


def resolve_destination(route):
    """Shadow only NFL Rushing Yards; preserve every current terminal route."""
    if route.sport_id == "nfl" and route.market_id == "rushing-yards":
        return canonical_loader.resolve_destination(route)
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
