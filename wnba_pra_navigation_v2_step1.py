"""WNBA PRA Navigation V2 — Step 1 foundation.

This module owns navigation state only.  It intentionally does not import any
WNBA schedule, player, market, projection, Monte Carlo, or sportsbook module.
Until later Navigation V2 steps are activated, the current frozen WNBA PRA
renderer remains the visible product surface.

The foundation is designed for fast drill-down:
- Slate is the default level.
- Game and Player identities are carried separately from presentation.
- Back transitions are deterministic.
- Query/session state can survive reruns and refreshes.
- Heavy page modules are never prefetched here.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

import streamlit as st


MODEL_VERSION = "WNBA PRA NAVIGATION V2 • STEP 1 FOUNDATION"

PAGE_SLATE = "slate"
PAGE_GAME = "game"
PAGE_PLAYER = "player"
VALID_PAGES = (PAGE_SLATE, PAGE_GAME, PAGE_PLAYER)

SESSION_PAGE = "ks_wnba_pra_nav_v2_page"
SESSION_GAME = "ks_wnba_pra_nav_v2_game"
SESSION_PLAYER = "ks_wnba_pra_nav_v2_player"
PERF_KEY = "ks_wnba_pra_nav_v2_step1_perf"

QUERY_PAGE = "wnba_pra_view"
QUERY_GAME = "wnba_pra_game"
QUERY_PLAYER = "wnba_pra_player"

NAVIGATION_CONTRACT = {
    "project": "WNBA Navigation V2",
    "step": "1/7",
    "scope": "navigation_state_and_route_ownership_only",
    "three_levels": [PAGE_SLATE, PAGE_GAME, PAGE_PLAYER],
    "default_level": PAGE_SLATE,
    "heavy_modules_prefetched": False,
    "page2_prefetched_from_page1": False,
    "page3_prefetched_from_page1": False,
    "page3_prefetched_from_page2": False,
    "legacy_surface_preserved_until_step2": True,
    "api_ownership_changed": False,
    "projection_math_changed": False,
    "market_math_changed": False,
    "ranking_changed": False,
    "qualification_changed": False,
    "monte_carlo_changed": False,
    "sportsbook_projection_influence": 0.0,
}


@dataclass(frozen=True)
class NavigationState:
    page: str = PAGE_SLATE
    game_id: str = ""
    player_id: str = ""

    @property
    def depth(self) -> int:
        if self.page == PAGE_PLAYER:
            return 3
        if self.page == PAGE_GAME:
            return 2
        return 1


def _clean(value: Any) -> str:
    return str(value or "").strip()


def normalize_state(page: Any, game_id: Any = "", player_id: Any = "") -> NavigationState:
    """Return a fail-closed three-level navigation state."""
    page_value = _clean(page).lower()
    game_value = _clean(game_id)
    player_value = _clean(player_id)

    if page_value not in VALID_PAGES:
        return NavigationState()

    if page_value == PAGE_GAME:
        if not game_value:
            return NavigationState()
        return NavigationState(page=PAGE_GAME, game_id=game_value)

    if page_value == PAGE_PLAYER:
        if not game_value:
            return NavigationState()
        if not player_value:
            return NavigationState(page=PAGE_GAME, game_id=game_value)
        return NavigationState(
            page=PAGE_PLAYER,
            game_id=game_value,
            player_id=player_value,
        )

    return NavigationState()


def _query_value(key: str) -> str:
    try:
        raw = st.query_params.get(key)
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return _clean(raw)


def _session_value(key: str) -> str:
    try:
        return _clean(st.session_state.get(key))
    except Exception:
        return ""


def current_state() -> NavigationState:
    """Resolve query-first state, then session state, then safe Slate default."""
    query_page = _query_value(QUERY_PAGE)
    query_game = _query_value(QUERY_GAME)
    query_player = _query_value(QUERY_PLAYER)

    page = query_page or _session_value(SESSION_PAGE) or PAGE_SLATE
    game_id = query_game or _session_value(SESSION_GAME)
    player_id = query_player or _session_value(SESSION_PLAYER)
    state = normalize_state(page, game_id, player_id)
    _write_session(state)
    return state


def _write_session(state: NavigationState) -> None:
    st.session_state[SESSION_PAGE] = state.page
    if state.game_id:
        st.session_state[SESSION_GAME] = state.game_id
    else:
        st.session_state.pop(SESSION_GAME, None)
    if state.player_id:
        st.session_state[SESSION_PLAYER] = state.player_id
    else:
        st.session_state.pop(SESSION_PLAYER, None)


def _write_query(state: NavigationState) -> None:
    try:
        st.query_params[QUERY_PAGE] = state.page
        if state.game_id:
            st.query_params[QUERY_GAME] = state.game_id
        else:
            st.query_params.pop(QUERY_GAME, None)
        if state.player_id:
            st.query_params[QUERY_PLAYER] = state.player_id
        else:
            st.query_params.pop(QUERY_PLAYER, None)
    except Exception:
        # Query persistence is convenience only. Session state remains the
        # authoritative in-app navigation state.
        pass


def set_state(state: NavigationState, *, sync_query: bool = True) -> NavigationState:
    safe = normalize_state(state.page, state.game_id, state.player_id)
    _write_session(safe)
    if sync_query:
        _write_query(safe)
    return safe


def go_to_slate(*, sync_query: bool = True) -> NavigationState:
    return set_state(NavigationState(), sync_query=sync_query)


def go_to_game(game_id: Any, *, sync_query: bool = True) -> NavigationState:
    return set_state(
        NavigationState(page=PAGE_GAME, game_id=_clean(game_id)),
        sync_query=sync_query,
    )


def go_to_player(
    game_id: Any,
    player_id: Any,
    *,
    sync_query: bool = True,
) -> NavigationState:
    return set_state(
        NavigationState(
            page=PAGE_PLAYER,
            game_id=_clean(game_id),
            player_id=_clean(player_id),
        ),
        sync_query=sync_query,
    )


def back_state(state: NavigationState) -> NavigationState:
    safe = normalize_state(state.page, state.game_id, state.player_id)
    if safe.page == PAGE_PLAYER:
        return NavigationState(page=PAGE_GAME, game_id=safe.game_id)
    return NavigationState()


def go_back(*, sync_query: bool = True) -> NavigationState:
    return set_state(back_state(current_state()), sync_query=sync_query)


def render_step1_foundation(legacy_renderer: Callable[[], Any]) -> Any:
    """Install state ownership while preserving the frozen WNBA PRA surface.

    Step 1 is intentionally invisible to the end user.  It proves that the new
    three-level router can sit in the production path without loading future
    Game/Player pages or modifying any WNBA analytics. Step 2 will replace only
    the Slate presentation.
    """
    started = perf_counter()
    state = current_state()

    # Record the lightweight navigation-dispatch cost so later speed steps can
    # compare against a real baseline.  No network/model work happens here.
    st.session_state[PERF_KEY] = {
        "page": state.page,
        "depth": state.depth,
        "game_selected": bool(state.game_id),
        "player_selected": bool(state.player_id),
        "future_page_prefetches": 0,
        "dispatch_ms_before_legacy": (perf_counter() - started) * 1000.0,
    }

    return legacy_renderer()


__all__ = [
    "MODEL_VERSION",
    "NAVIGATION_CONTRACT",
    "NavigationState",
    "PAGE_GAME",
    "PAGE_PLAYER",
    "PAGE_SLATE",
    "PERF_KEY",
    "QUERY_GAME",
    "QUERY_PAGE",
    "QUERY_PLAYER",
    "SESSION_GAME",
    "SESSION_PAGE",
    "SESSION_PLAYER",
    "VALID_PAGES",
    "back_state",
    "current_state",
    "go_back",
    "go_to_game",
    "go_to_player",
    "go_to_slate",
    "normalize_state",
    "render_step1_foundation",
    "set_state",
]
