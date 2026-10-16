"""MONSTER CFB Game Total Page 1 — unified repair production overlay.

This thin overlay sits above the frozen Step-9 production router. It changes only
the Page-1 native owner pointer to V45 for the duration of one render. Selected
Page 2 keeps the frozen Step-9 direct fast path, and every other route continues
through the prior production router unchanged.
"""
from __future__ import annotations

from threading import RLock
from typing import Any

import streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1 as prior
import streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1 as cfb_prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER • CFB GAME TOTAL PAGE1 UNIFIED REPAIR V1"
PRIOR_RUNTIME = "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1"
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


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> Any:
    """Temporarily advance only Page 1; frozen Step 9 owns Page 2 unchanged."""
    with _ROUTE_LOCK:
        original_page1 = cfb_prior.PAGE1_NATIVE_ROUTE
        cfb_prior.PAGE1_NATIVE_ROUTE = PAGE1_REPAIR_ROUTE
        try:
            return prior.render_app()
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
    "PRIOR_RUNTIME",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
