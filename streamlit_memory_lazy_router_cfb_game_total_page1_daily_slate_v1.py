"""CFB Game Total Page 1 — Daily Slate routing context V1.

Temporarily rebinds only the unselected Game Total Page-1 owner to the new
Daily Slate. The selected-game SAME_PAGE_RUNTIME is deliberately untouched so
Page 2/Page 3 downstream compatibility remains owned by the existing frozen
selected-game route.
"""
from __future__ import annotations

from contextlib import contextmanager
from threading import RLock
from typing import Any, Callable

import cfb_game_total_page1_daily_slate_runtime_fallback_r1 as daily_fallback
import cfb_game_total_page1_polish_r4 as page1_polish
import streamlit_memory_lazy_router_cfb_game_total_page1_unified_repair_v1 as page1_repair
import streamlit_memory_lazy_router_v1 as root

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
FRESH_IMPORT_CROSSCHECK_ENABLED = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_LOCK = RLock()


def _empty_primary_crosscheck(delegate: Callable[[Any], dict[str, Any]]) -> Callable[[Any], dict[str, Any]]:
    """Wrap one Daily Slate loader without changing any analysis/model logic."""
    if getattr(delegate, "_cfbgt_daily_empty_primary_crosscheck", False):
        return delegate

    def load_day(day):
        payload = dict(delegate(day))
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

    load_day._cfbgt_daily_empty_primary_crosscheck = True  # type: ignore[attr-defined]
    load_day._cfbgt_daily_empty_primary_delegate = delegate  # type: ignore[attr-defined]
    return load_day


@contextmanager
def _install_empty_primary_crosscheck():
    """Patch the currently loaded Page-1 owner for non-purging renders."""
    original_load_day = daily_fallback.page._load_day
    wrapped = _empty_primary_crosscheck(original_load_day)
    daily_fallback.page._load_day = wrapped
    polish_originals = page1_polish.install_into(daily_fallback.page)
    try:
        yield
    finally:
        page1_polish.restore_from(daily_fallback.page, polish_originals)
        if daily_fallback.page._load_day is wrapped:
            daily_fallback.page._load_day = original_load_day


@contextmanager
def _install_fresh_import_crosscheck():
    """Patch the fresh Page-1 module created after the root router purges cfb_*."""
    original_import = root._import
    patched_modules: list[tuple[Any, ...]] = []

    def import_with_daily_slate_crosscheck(name: str):
        module = original_import(name)
        if str(name) != PAGE1_DAILY_SLATE_ROUTE:
            return module

        original_load_day = getattr(module, "_load_day", None)
        if not callable(original_load_day):
            return module
        wrapped = _empty_primary_crosscheck(original_load_day)
        if wrapped is not original_load_day:
            module._load_day = wrapped
        polish_originals = page1_polish.install_into(module)
        patched_modules.append((module, original_load_day, wrapped, polish_originals))
        return module

    root._import = import_with_daily_slate_crosscheck
    try:
        yield
    finally:
        root._import = original_import
        for module, original_load_day, wrapped, polish_originals in reversed(patched_modules):
            page1_polish.restore_from(module, polish_originals)
            if getattr(module, "_load_day", None) is wrapped:
                module._load_day = original_load_day


@contextmanager
def install_daily_slate_page1():
    """Install the canonical Daily Slate only for unselected Page 1."""
    with _LOCK:
        original_page1_route = page1_repair.PAGE1_REPAIR_ROUTE
        page1_repair.PAGE1_REPAIR_ROUTE = PAGE1_DAILY_SLATE_ROUTE
        try:
            with daily_fallback._install_runtime_fallback():
                with _install_empty_primary_crosscheck():
                    with _install_fresh_import_crosscheck():
                        yield
        finally:
            page1_repair.PAGE1_REPAIR_ROUTE = original_page1_route


__all__ = [
    "ACTIVE_MARKER",
    "FALLBACK_NETWORK_ON_EMPTY_PRIMARY",
    "FALLBACK_NETWORK_ONLY_WHEN_PRIMARY_UNAVAILABLE",
    "FRESH_IMPORT_CROSSCHECK_ENABLED",
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
