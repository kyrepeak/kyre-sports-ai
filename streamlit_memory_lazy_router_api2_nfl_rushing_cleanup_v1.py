"""API 2 NFL Rushing Yards compact-cleanup terminal successor V1.

Additive over the frozen universal NFL Active-Slate terminal. During one render
only, it points the existing NFL Rushing Yards route at V17, then restores the
frozen route map. All other NFL markets and all other sports delegate unchanged.
"""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_api2_nfl_active_slate_v1 as prior
import streamlit_memory_lazy_router_v187 as route_owner

MODEL_VERSION = "API2 NFL RUSHING CLEANUP V1 • TERMINAL SUCCESSOR"
FROZEN_PARENT = "streamlit_memory_lazy_router_api2_nfl_active_slate_v1"
ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v17"
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> Any:
    previous = route_owner.PROP_HUBS.get("Rushing Yards")
    route_owner.PROP_HUBS["Rushing Yards"] = ACTIVE_RUSHING_YARDS_HUB
    try:
        return prior.render_app()
    finally:
        if previous is None:
            route_owner.PROP_HUBS.pop("Rushing Yards", None)
        else:
            route_owner.PROP_HUBS["Rushing Yards"] = previous


__all__ = [
    "ACTIVE_RUSHING_YARDS_HUB",
    "FROZEN_PARENT",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
