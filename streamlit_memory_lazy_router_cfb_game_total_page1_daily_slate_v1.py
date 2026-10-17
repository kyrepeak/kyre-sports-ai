"""CFB Game Total Page 1 — Daily Slate routing context V1.

Temporarily rebinds only the unselected Game Total Page-1 owner to the new
Daily Slate. The selected-game SAME_PAGE_RUNTIME is deliberately untouched so
Page 2/Page 3 downstream compatibility remains owned by the existing frozen
selected-game route.
"""
from __future__ import annotations

from contextlib import contextmanager
from threading import RLock

import cfb_game_total_page1_daily_slate_runtime_fallback_r1 as daily_fallback
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
FALLBACK_NETWORK_ONLY_WHEN_PRIMARY_UNAVAILABLE = False
FALLBACK_NETWORK_ON_EMPTY_PRIMARY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_LOCK = RLock()


@contextmanager
def _install_empty_primary_crosscheck():
    """Do not trust a non-throwing empty primary slate without a fallback check."""
    original_load_day = daily_fallback.page._load_day

    def load_day(day):
        payload = dict(original_load_day(day))
        if int(payload.get("game_count") or 0) > 0 or payload.get("games"):
            return payload

        try:
            fallback_payload = dict(daily_fallback.build_requests_fallback_payload(day))
        except Exception:
            payload["primary_empty"] = True
            return payload

        if int(fallback_payload.get("game_count") or 0) > 0 or fallback_payload.get("games"):
            fallback_payload["primary_empty"] = True
            fallback_payload["transport"] = "requests_espn_fallback"
            return fallback_payload

        payload["primary_empty"] = True
        return payload

    daily_fallback.page._load_day = load_day
    try:
        yield
    finally:
        daily_fallback.page._load_day = original_load_day


@contextmanager
def install_daily_slate_page1():
    """Install the canonical Daily Slate only for unselected Page 1."""
    with _LOCK:
        original_page1_route = page1_repair.PAGE1_REPAIR_ROUTE
        page1_repair.PAGE1_REPAIR_ROUTE = PAGE1_DAILY_SLATE_ROUTE
        try:
            with daily_fallback._install_runtime_fallback():
                with _install_empty_primary_crosscheck():
                    yield
        finally:
            page1_repair.PAGE1_REPAIR_ROUTE = original_page1_route


__all__ = [
    "ACTIVE_MARKER",
    "FALLBACK_NETWORK_ON_EMPTY_PRIMARY",
    "FALLBACK_NETWORK_ONLY_WHEN_PRIMARY_UNAVAILABLE",
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
