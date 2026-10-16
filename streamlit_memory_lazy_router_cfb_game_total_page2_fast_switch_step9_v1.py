"""MONSTER CFB Game Total Page 2 Step 9 — fast matchup switching overlay.

Exact selected CFB Game Total events bypass Page-1-only installers and the
inherited full router traversal, then render the already-frozen Step-8 Page-2
runtime directly. Every other route delegates byte-for-behavior to the current
production router owner.

This layer is routing/performance-only. It does not change providers, model,
projection, probability, ranking, selection, sportsbook influence, or any
frozen Step-1-through-Step-8 product logic.
"""
from __future__ import annotations

import importlib
from typing import Any

import streamlit_memory_lazy_router_nba_spread_step2_activation_v1 as prior
import streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1 as cfb_prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER • CFB GAME TOTAL PAGE2 STEP9 FAST SWITCH V1"
PRIOR_RUNTIME = "streamlit_memory_lazy_router_nba_spread_step2_activation_v1"
CFB_ROUTE_OWNER = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1"
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _current_event_id() -> str:
    """Read the current exact event from the query on every render."""
    return cfb_prior._query_value(cfb_prior.EVENT_QUERY_KEY)


def _selected_game_total() -> bool:
    """Fail closed unless the current exact event still owns the selected route."""
    event_id = _current_event_id()
    if not event_id:
        return False
    if cfb_prior._query_value(cfb_prior.SELECTOR_SYNC_QUERY_KEY) != event_id:
        return False
    return bool(cfb_prior._selected_game_total() and _current_event_id() == event_id)


def _render_selected_page_fast() -> Any:
    """Render frozen Step-8 Page 2 directly while guarding against stale switches."""
    event_id = _current_event_id()
    if not event_id:
        return prior.render_app()

    cfb_prior._render_page1_navigation_shell()
    if _current_event_id() != event_id:
        return prior.render_app()

    page = importlib.import_module(cfb_prior.PAGE2_RUNTIME)
    if _current_event_id() != event_id:
        return prior.render_app()

    return page.render_cfb_hub(
        cfb_prior.GAME_TOTAL_MARKET,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def render_app() -> Any:
    if _selected_game_total():
        return _render_selected_page_fast()
    return prior.render_app()


__all__ = [
    "CFB_ROUTE_OWNER",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PRIOR_RUNTIME",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_current_event_id",
    "_render_selected_page_fast",
    "_selected_game_total",
    "record_bootstrap_import_ms",
    "render_app",
]
