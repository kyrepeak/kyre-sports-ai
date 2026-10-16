"""MONSTER CFB Game Total Page 1 — unified repair bridge.

This helper changes only the Step-8 router's Page-1 native owner pointer for the
duration of a delegated non-selected render. The frozen Step-9 router keeps
selected Page 2 ahead of this helper, so the fast Page-2 path is unchanged.
"""
from __future__ import annotations

from threading import RLock
from typing import Any, Callable

import streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1 as cfb_prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER • CFB GAME TOTAL PAGE1 UNIFIED REPAIR BRIDGE V1"
PAGE1_REPAIR_ROUTE = "cfb_game_total_clean_page_v45"
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_PAGE2 = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ROUTE_LOCK = RLock()


def render_with_page1_repair(delegate: Callable[[], Any]) -> Any:
    """Advance only the native Page-1 owner while a prior router renders."""
    with _ROUTE_LOCK:
        original_page1 = cfb_prior.PAGE1_NATIVE_ROUTE
        cfb_prior.PAGE1_NATIVE_ROUTE = PAGE1_REPAIR_ROUTE
        try:
            return delegate()
        finally:
            cfb_prior.PAGE1_NATIVE_ROUTE = original_page1


__all__ = [
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE2",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PAGE1_REPAIR_ROUTE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_with_page1_repair",
]
