"""CFB Game Total page-order + slate-cleanup routing context V1.

Installs two temporary CFB-only route identities for one render:
- unselected Game Total -> clean slate Page 2 owner;
- exact selected Game Total -> full analysis Page 1 owner.

The frozen CFB router and Page-1 bridge are restored immediately after render.
No other sport/market behavior or model/data logic is changed.
"""
from __future__ import annotations

from contextlib import contextmanager
from threading import RLock

import streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_frozen_v1 as cfb_route
import streamlit_memory_lazy_router_cfb_game_total_page1_unified_repair_v1 as page1_repair

MODEL_VERSION = "CFB GAME TOTAL PAGE ORDER CLEANUP ROUTER V1"
ACTIVE_MARKER = "CFB_GAME_TOTAL_PAGE_ORDER_CLEANUP_V1_ACTIVE"
PAGE1_SELECTED_RUNTIME = "cfb_game_total_page1_selected_analysis_v1"
PAGE2_SLATE_RUNTIME = "cfb_game_total_page2_clean_slate_v1"
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_LOCK = RLock()


@contextmanager
def install_page_order_cleanup():
    """Temporarily reverse the human-facing page semantics for CFB Game Total."""
    with _LOCK:
        original_selected_runtime = cfb_route.SAME_PAGE_RUNTIME
        original_slate_runtime = page1_repair.PAGE1_REPAIR_ROUTE
        cfb_route.SAME_PAGE_RUNTIME = "cfb_game_total_page1_selected_analysis_v1"
        page1_repair.PAGE1_REPAIR_ROUTE = "cfb_game_total_page2_clean_slate_v1"
        try:
            yield
        finally:
            page1_repair.PAGE1_REPAIR_ROUTE = original_slate_runtime
            cfb_route.SAME_PAGE_RUNTIME = original_selected_runtime


__all__ = [
    "ACTIVE_MARKER",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PAGE1_SELECTED_RUNTIME",
    "PAGE2_SLATE_RUNTIME",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "install_page_order_cleanup",
]
