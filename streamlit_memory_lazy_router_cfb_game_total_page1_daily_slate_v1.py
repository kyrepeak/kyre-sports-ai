"""CFB Game Total Page 1 — Daily Slate routing context V1.

Temporarily rebinds only the unselected Game Total Page-1 owner to the new
Daily Slate. The selected-game SAME_PAGE_RUNTIME is deliberately untouched so
Page 2/Page 3 downstream compatibility remains owned by the existing frozen
selected-game route.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Mapping

import requests
import streamlit as st

import cfb_game_total_page1_daily_slate_runtime_fallback_r1 as daily_fallback
import cfb_game_total_page1_polish_r4 as page1_polish
import cfb_game_total_page1_market_truth_r5 as page1_market_truth
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

ACTION_API_URL = "https://api.actionnetwork.com/web/v2/scoreboard/ncaaf?bookIds=15,30,68,69,71,75,79,123,2988"
_ACTION_API_BOOKS = {
    "15": {"display_name": "Consensus"}, "30": {"display_name": "Open"},
    "68": {"display_name": "DK NJ", "parent_name": "DraftKings"},
    "69": {"display_name": "FanDuel NJ", "parent_name": "FanDuel"},
    "71": {"display_name": "BetRivers NJ", "parent_name": "BetRivers"},
    "75": {"display_name": "BetMGM NJ", "parent_name": "BetMGM"},
    "79": {"display_name": "bet365 NJ", "parent_name": "bet365"},
    "123": {"display_name": "Caesars NJ", "parent_name": "Caesars"},
    "2988": {"display_name": "Fanatics NJ", "parent_name": "Fanatics"},
}


def _parse_action_api(payload: Mapping[str, Any], observed_at_utc: str | None = None) -> list[dict[str, Any]]:
    games = payload.get("games") if isinstance(payload, Mapping) else None
    if not isinstance(games, list):
        return []
    observed = observed_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    parsed: list[dict[str, Any]] = []
    for raw in games:
        if not isinstance(raw, Mapping):
            continue
        teams = [t for t in raw.get("teams") or [] if isinstance(t, Mapping)]
        away = next((t for t in teams if str(t.get("id")) == str(raw.get("away_team_id"))), None)
        home = next((t for t in teams if str(t.get("id")) == str(raw.get("home_team_id"))), None)
        if away is None or home is None:
            continue
        observations = page1_market_truth._action_observations(raw, _ACTION_API_BOOKS, observed)
        if observations:
            parsed.append({
                "action_event_id": page1_market_truth._clean(raw.get("id")),
                "start_time_utc": page1_market_truth._clean(raw.get("start_time")),
                "away_aliases": sorted(page1_market_truth._action_team_aliases(away)),
                "home_aliases": sorted(page1_market_truth._action_team_aliases(home)),
                "observations": observations,
            })
    return parsed


@st.cache_data(ttl=30, show_spinner=False)
def _fetch_action_json_board() -> list[dict[str, Any]]:
    response = requests.get(
        ACTION_API_URL,
        timeout=12.0,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    response.raise_for_status()
    return _parse_action_api(response.json())


@contextmanager
def _install_action_json_primary():
    original = page1_market_truth.fetch_action_market_board

    def fetch():
        try:
            direct = _fetch_action_json_board()
            if direct:
                return direct
        except Exception:
            pass
        return original()

    page1_market_truth.fetch_action_market_board = fetch
    try:
        yield
    finally:
        if page1_market_truth.fetch_action_market_board is fetch:
            page1_market_truth.fetch_action_market_board = original


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
    market_originals = page1_market_truth.install_into(daily_fallback.page)
    try:
        yield
    finally:
        page1_market_truth.restore_from(daily_fallback.page, market_originals)
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
        market_originals = page1_market_truth.install_into(module)
        patched_modules.append((module, original_load_day, wrapped, polish_originals, market_originals))
        return module

    root._import = import_with_daily_slate_crosscheck
    try:
        yield
    finally:
        root._import = original_import
        for module, original_load_day, wrapped, polish_originals, market_originals in reversed(patched_modules):
            page1_market_truth.restore_from(module, market_originals)
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
                with _install_action_json_primary():
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
