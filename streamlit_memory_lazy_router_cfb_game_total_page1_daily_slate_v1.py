"""CFB Game Total Page 1 — Daily Slate routing context V1.

Temporarily rebinds only the unselected Game Total Page-1 owner to the new
Daily Slate. The selected-game SAME_PAGE_RUNTIME is deliberately untouched so
Page 2/Page 3 downstream compatibility remains owned by the existing frozen
selected-game route.
"""
from __future__ import annotations

from contextlib import contextmanager
from threading import RLock

import streamlit_memory_lazy_router_cfb_game_total_page1_unified_repair_v1 as page1_repair

MODEL_VERSION = "CFB GAME TOTAL PAGE1 DAILY SLATE ROUTER V1"
ACTIVE_MARKER = "CFB_GAME_TOTAL_PAGE1_DAILY_SLATE_ROUTER_V1_ACTIVE"
PAGE1_DAILY_SLATE_ROUTE = "cfb_game_total_page1_daily_slate_v1"
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_SELECTED_GAME_RUNTIME = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_LOCK = RLock()


@contextmanager
def install_daily_slate_page1():
    """Install the canonical Daily Slate only for unselected Page 1."""
    with _LOCK:
        original_page1_route = page1_repair.PAGE1_REPAIR_ROUTE
        page1_repair.PAGE1_REPAIR_ROUTE = PAGE1_DAILY_SLATE_ROUTE
        try:
            yield
        finally:
            page1_repair.PAGE1_REPAIR_ROUTE = original_page1_route


__all__ = [
    "ACTIVE_MARKER",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTED_GAME_RUNTIME",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PAGE1_DAILY_SLATE_ROUTE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "install_daily_slate_page1",
]
