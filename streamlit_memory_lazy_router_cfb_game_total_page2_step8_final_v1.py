"""CFB Game Total Page 2 Step 8 — final selected-event router overlay.

The existing Page-1 slate remains the owner until an exact CFB Game Total event
is selected. Only then does this wrapper temporarily point the known exact
Game-Total route owners at the frozen Step-8 Page-2 runtime. All pointers are
restored after the render call; other sports/markets continue through the frozen
parent router unchanged.

Games on This Day Steps 2-4 are additive Page-1-only presentation installers.
Native Website Routing Step 1 established V39, native Page-1 Shell Step 3
advanced the Page-1 owner to V40, Phoenix Day Selector Step 4 advanced it to
V41, Games-on-Day Data Step 5 advanced it to V42, and Game Cards Step 6 advances
only that Page-1 owner to V43. All Page-1 additions are bypassed whenever Page 2
owns an exact selected event.

Step-8 finalization guard: Page 1 must never publish an exact-event query merely
because the frozen selector internally defaults to the first game. A real card
tap carries SELECTOR_SYNC_QUERY_KEY and is required for Page-2 activation; an
auto-published event without that tap marker is removed after the Page-1 render.

MONSTER shell-integration Step 1 keeps the exact V43 Page-1 content owner but
renders it through the shared V1 KYRE SPORTS AI shell. The temporary selector
and renderer seams are restored after every render, and exact selected-event
Page 2 remains owned by the frozen Step-8 runtime.
"""
from __future__ import annotations

from threading import RLock
from typing import Any, Callable

import streamlit as st

import streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration as frozen_parent
import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v160 as render_owner
import streamlit_memory_lazy_router_v181 as live_owner
import streamlit_memory_lazy_router_v190 as cfb_router
from cfb_game_total_games_on_day_step2_visual_v1 import install_games_on_day_step2_visual
from cfb_game_total_games_on_day_step3_details_v1 import install_games_on_day_step3_details
from cfb_game_total_games_on_day_step4_interaction_mobile_v1 import install_games_on_day_step4_interaction_mobile

MODEL_VERSION = "KYRE STREAMLIT ROUTER • CFB GAME TOTAL PAGE2 STEP8 FINAL V1"
FROZEN_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration"
PAGE1_NATIVE_ROUTE = "cfb_game_total_clean_page_v43"
PAGE2_RUNTIME = "cfb_game_total_page2_step8_final_runtime_v1"
EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"
SELECTOR_SYNC_QUERY_KEY = "ks_cfb_game_total_selector_sync"
GAME_TOTAL_MARKET = "Game Total"
CFB_SPORT = "CFB"
CFB_SPORT_LABEL = "College Football"
CFB_SHELL_MARKETS = ("Moneyline", "Over/Under", "Game Total", "Top Picks")
CFB_MARKET_SESSION_KEY = "ks_cfb_market_touch"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_MARKET_OWNERSHIP = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_ROUTE_POINTER_LOCK = RLock()


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
    """Activate Page 2 only for an exact event produced by a real card tap."""
    event_id = _query_value(EVENT_QUERY_KEY)
    sync_id = _query_value(SELECTOR_SYNC_QUERY_KEY)
    if not event_id or sync_id != event_id:
        return False
    if not live_owner._game_total_route_active():
        live_owner._restore_game_total_route_from_query()
    return bool(
        live_owner._game_total_route_active()
        and _query_value(EVENT_QUERY_KEY) == event_id
        and _query_value(SELECTOR_SYNC_QUERY_KEY) == event_id
    )


def _make_page1_selectbox_bridge(delegate: Callable[..., Any]) -> Callable[..., Any]:
    """Extend the already-active shared shell with exact CFB controls only."""
    if getattr(delegate, "_cfb_game_total_step1_shell_bridge", False):
        return delegate

    def _bridge(label: Any, options: Any, *args: Any, **kwargs: Any):
        if label == "🏟️ Sport":
            extended = list(options)
            if CFB_SPORT_LABEL not in extended:
                extended.append(CFB_SPORT_LABEL)
            selected = delegate(label, extended, *args, **kwargs)
            if str(selected) != CFB_SPORT_LABEL:
                live_owner._clear_game_total_route_query()
            return selected

        if (
            label == "🎯 NFL Market"
            and str(st.session_state.get("ks_sport_touch") or "") == CFB_SPORT_LABEL
        ):
            if str(st.session_state.get(CFB_MARKET_SESSION_KEY) or "") not in CFB_SHELL_MARKETS:
                st.session_state.pop(CFB_MARKET_SESSION_KEY, None)
            clean_kwargs = dict(kwargs)
            clean_kwargs.pop("key", None)
            clean_kwargs.pop("index", None)
            selected = delegate(
                "🎯 CFB Market",
                list(CFB_SHELL_MARKETS),
                *args,
                key=CFB_MARKET_SESSION_KEY,
                **clean_kwargs,
            )
            if str(selected) == GAME_TOTAL_MARKET:
                live_owner._persist_game_total_route_query()
            else:
                live_owner._clear_game_total_route_query()
            return selected

        return delegate(label, options, *args, **kwargs)

    _bridge._cfb_game_total_step1_shell_bridge = True  # type: ignore[attr-defined]
    _bridge._cfb_game_total_step1_delegate = delegate  # type: ignore[attr-defined]
    return _bridge


def _make_page1_renderer_bridge(delegate: Callable[[str], Any]) -> Callable[[str], Any]:
    """Own only exact CFB Game Total; hand every other sport back unchanged."""
    if getattr(delegate, "_cfb_game_total_step1_shell_bridge", False):
        return delegate

    def _bridge(market: str):
        sport = str(st.session_state.get("ks_sport_touch") or "")
        if sport == CFB_SPORT_LABEL and market == GAME_TOTAL_MARKET:
            return _render_page1_game_total(market)
        if sport == CFB_SPORT_LABEL and market != GAME_TOTAL_MARKET:
            live_owner._clear_game_total_route_query()
            st.rerun()
            return None
        if sport != CFB_SPORT_LABEL:
            return delegate(market)
        return delegate(market)

    _bridge._cfb_game_total_step1_shell_bridge = True  # type: ignore[attr-defined]
    _bridge._cfb_game_total_step1_delegate = delegate  # type: ignore[attr-defined]
    return _bridge


def _render_page1_game_total(market: str) -> Any:
    """Render V43 inside the shared shell without changing its product logic."""
    if (
        str(st.session_state.get("ks_sport_touch") or "") != CFB_SPORT_LABEL
        or str(market or "") != GAME_TOTAL_MARKET
    ):
        raise RuntimeError("CFB_GAME_TOTAL_STEP1_SHELL_ROUTE_IDENTITY_MISMATCH")
    live_owner._persist_game_total_route_query()
    page = root._import(PAGE1_NATIVE_ROUTE)
    return page.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def _render_page1_in_shared_shell() -> Any:
    """Run one exact Game Total Page-1 render through the universal shell."""
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES
    root.st.selectbox = _make_page1_selectbox_bridge(original_selectbox)
    root._render_nfl = _make_page1_renderer_bridge(original_render_nfl)
    if "cfb_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("cfb_",)
    try:
        return root.render_app()
    finally:
        root.st.selectbox = original_selectbox
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def _render_native_page1() -> Any:
    """Advance only the exact Page-1 owner for one render, then restore it."""
    with _ROUTE_POINTER_LOCK:
        original_page1 = cfb_router.GAME_TOTAL_PAGE
        cfb_router.GAME_TOTAL_PAGE = PAGE1_NATIVE_ROUTE
        try:
            if not live_owner._game_total_route_active():
                return frozen_parent.render_app()
            return _render_page1_in_shared_shell()
        finally:
            cfb_router.GAME_TOTAL_PAGE = original_page1


def _clear_auto_event_after_page1() -> bool:
    """Remove only a selector-created event; preserve a real card-tap handoff."""
    if _query_value(SELECTOR_SYNC_QUERY_KEY):
        return False
    if not _query_value(EVENT_QUERY_KEY):
        return False
    try:
        del st.query_params[EVENT_QUERY_KEY]
    except Exception:
        return False
    return True


def render_app() -> Any:
    if not _selected_game_total():
        install_games_on_day_step2_visual()
        install_games_on_day_step3_details()
        install_games_on_day_step4_interaction_mobile()
        rendered = _render_native_page1()
        _clear_auto_event_after_page1()
        return rendered

    with _ROUTE_POINTER_LOCK:
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
    "CFB_MARKET_SESSION_KEY",
    "CFB_SHELL_MARKETS",
    "CFB_SPORT",
    "CFB_SPORT_LABEL",
    "EVENT_QUERY_KEY",
    "SELECTOR_SYNC_QUERY_KEY",
    "FROZEN_ROUTER",
    "GAME_TOTAL_MARKET",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PAGE1_NATIVE_ROUTE",
    "PAGE2_RUNTIME",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_clear_auto_event_after_page1",
    "_make_page1_renderer_bridge",
    "_make_page1_selectbox_bridge",
    "_render_native_page1",
    "_render_page1_game_total",
    "_render_page1_in_shared_shell",
    "record_bootstrap_import_ms",
    "render_app",
]