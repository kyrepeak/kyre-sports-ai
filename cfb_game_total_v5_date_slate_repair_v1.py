"""CFB Game Total V5 date/slate repair V1.

This additive bridge restores the already-certified Daily Slate fallback context
inside Universal Runtime V5 and keeps selected-game Page 2 frozen. It also emits
canonical V5 route parameters alongside legacy Game Total keys so a tapped game
retains exact identity across reruns and direct reloads.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any, Mapping, MutableMapping
from urllib.parse import urlencode

import streamlit as st

import streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1 as daily_router

MODEL_VERSION = "API2 CFB GAME TOTAL V5 DATE + SLATE REPAIR V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_SELECTED_GAME_RUNTIME = False

SPORT_QUERY_KEY = "sport"
MARKET_QUERY_KEY = "market"
DATE_QUERY_KEY = "date"
GAME_QUERY_KEY = "game_id"
LEGACY_SPORT_QUERY_KEY = "ks_sport"
LEGACY_MARKET_QUERY_KEY = "ks_cfb_market"
LEGACY_DATE_QUERY_KEY = "ks_cfb_game_total_date"
LEGACY_EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"
LEGACY_SELECTOR_QUERY_KEY = "ks_cfb_game_total_selector_sync"


def _scalar(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""
    return str(value or "").strip()


def canonical_view_game_href(game: Mapping[str, Any], selected_day: date) -> str:
    """Build one exact-game URL understood by both V5 and frozen Game Total code."""
    event_id = _scalar(game.get("event_id"))
    if not event_id:
        return ""
    day = selected_day.isoformat()
    params = {
        SPORT_QUERY_KEY: "cfb",
        MARKET_QUERY_KEY: "game-total",
        DATE_QUERY_KEY: day,
        GAME_QUERY_KEY: event_id,
        LEGACY_SPORT_QUERY_KEY: "College Football",
        LEGACY_MARKET_QUERY_KEY: "Game Total",
        LEGACY_DATE_QUERY_KEY: day,
        LEGACY_EVENT_QUERY_KEY: event_id,
        LEGACY_SELECTOR_QUERY_KEY: event_id,
    }
    return "?" + urlencode(params)


def selected_event_id(
    route: Any,
    *,
    query: Mapping[str, Any] | None = None,
    session: Mapping[str, Any] | None = None,
) -> str:
    """Resolve exact selected-game identity, preferring canonical V5 route state."""
    query_values = st.query_params if query is None else query
    session_values = st.session_state if session is None else session
    route_params = getattr(route, "params", {})
    if not isinstance(route_params, Mapping):
        route_params = {}
    for value in (
        route_params.get(GAME_QUERY_KEY),
        query_values.get(GAME_QUERY_KEY),
        query_values.get(LEGACY_EVENT_QUERY_KEY),
        query_values.get(LEGACY_SELECTOR_QUERY_KEY),
        session_values.get(LEGACY_EVENT_QUERY_KEY),
        session_values.get(LEGACY_SELECTOR_QUERY_KEY),
    ):
        event_id = _scalar(value)
        if event_id:
            return event_id
    return ""


def sync_selected_event_id(
    event_id: str,
    route: Any,
    *,
    query: MutableMapping[str, Any] | None = None,
    session: MutableMapping[str, Any] | None = None,
) -> None:
    """Mirror canonical selection into frozen Page-2 keys without changing ownership."""
    exact = _scalar(event_id)
    if not exact:
        return
    query_values = st.query_params if query is None else query
    session_values = st.session_state if session is None else session
    route_params = getattr(route, "params", {})
    if not isinstance(route_params, Mapping):
        route_params = {}
    selected_day = _scalar(route_params.get(DATE_QUERY_KEY) or query_values.get(DATE_QUERY_KEY) or query_values.get(LEGACY_DATE_QUERY_KEY))

    for key, value in (
        (GAME_QUERY_KEY, exact),
        (LEGACY_EVENT_QUERY_KEY, exact),
        (LEGACY_SELECTOR_QUERY_KEY, exact),
    ):
        query_values[key] = value
    if selected_day:
        query_values[DATE_QUERY_KEY] = selected_day
        query_values[LEGACY_DATE_QUERY_KEY] = selected_day
    session_values[LEGACY_EVENT_QUERY_KEY] = exact
    session_values[LEGACY_SELECTOR_QUERY_KEY] = exact


@contextmanager
def install_page1_runtime(page1_module: Any):
    """Install certified empty-primary fallback and canonical links for Page 1 only."""
    original_href = getattr(page1_module, "view_game_href")
    page1_module.view_game_href = canonical_view_game_href
    try:
        with daily_router.install_daily_slate_page1():
            yield page1_module
    finally:
        if getattr(page1_module, "view_game_href", None) is canonical_view_game_href:
            page1_module.view_game_href = original_href


__all__ = [
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTED_GAME_RUNTIME",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "canonical_view_game_href",
    "install_page1_runtime",
    "selected_event_id",
    "sync_selected_event_id",
]
