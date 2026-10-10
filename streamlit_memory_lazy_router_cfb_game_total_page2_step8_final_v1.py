"""CFB Game Total Page 2 Step 8 — final selected-event router overlay.

The existing Page-1 slate remains the owner until an exact CFB Game Total event
is selected. Only then does this wrapper temporarily point the known exact
Game-Total route owners at the frozen Step-8 Page-2 runtime. All pointers are
restored after the render call; other sports/markets continue through the frozen
parent router unchanged.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration as frozen_parent
import streamlit_memory_lazy_router_v160 as render_owner
import streamlit_memory_lazy_router_v181 as live_owner
import streamlit_memory_lazy_router_v190 as cfb_router

MODEL_VERSION = "KYRE STREAMLIT ROUTER • CFB GAME TOTAL PAGE2 STEP8 FINAL V1"
FROZEN_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration"
PAGE2_RUNTIME = "cfb_game_total_page2_step8_final_runtime_v1"
EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"
GAME_TOTAL_MARKET = "Game Total"
CFB_SPORT = "CFB"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_MARKET_OWNERSHIP = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def _query_value(key: str) -> str:
    try:
        raw: Any = st.query_params.get(key)
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _selected_game_total() -> bool:
    """Activate Page 2 once a valid Game-Total query owns an exact event."""
    if not _query_value(EVENT_QUERY_KEY):
        return False
    if not live_owner._game_total_route_active():
        live_owner._restore_game_total_route_from_query()
    return bool(live_owner._game_total_route_active() and _query_value(EVENT_QUERY_KEY))


def render_app() -> Any:
    if not _selected_game_total():
        return frozen_parent.render_app()

    original_cfb_page = cfb_router.GAME_TOTAL_PAGE
    original_live_page = live_owner.ACTIVE_PAGE
    original_render_page = render_owner.ACTIVE_PAGE

    cfb_router.GAME_TOTAL_PAGE = PAGE2_RUNTIME
    live_owner.ACTIVE_PAGE = PAGE2_RUNTIME
    render_owner.ACTIVE_PAGE = PAGE2_RUNTIME
    try:
        return frozen_parent.render_app()
    finally:
        cfb_router.GAME_TOTAL_PAGE = original_cfb_page
        live_owner.ACTIVE_PAGE = original_live_page
        render_owner.ACTIVE_PAGE = original_render_page


__all__ = [
    "CFB_SPORT",
    "EVENT_QUERY_KEY",
    "FROZEN_ROUTER",
    "GAME_TOTAL_MARKET",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PAGE2_RUNTIME",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
