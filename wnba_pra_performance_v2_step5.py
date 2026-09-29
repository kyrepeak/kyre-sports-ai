"""WNBA Navigation V2 — Step 5 performance + lazy-transition layer.

Performance-only wrapper over frozen Steps 1-4.

Repairs two transport/cache costs without changing any frozen basketball output:
1) navigation buttons are registered with native Streamlit on_click callbacks, so
   the button's normal rerun enters the destination route without an explicit
   second st.rerun roundtrip;
2) Player Intelligence reuses the global consumer snapshot separately from
   per-player history inside the same Streamlit session, so switching players
   does not reread the same consumer board.

Only the exact user-selected next page may be prefetched, inside the click
callback. There is no speculative/background prefetch.
"""
from __future__ import annotations

import copy
from functools import partial
import time
from typing import Any, Callable, Mapping

import streamlit as st

import wnba_pra_navigation_v2_step1 as navigation
import wnba_pra_slate_v2_step2 as slate
import wnba_pra_game_center_v2_step3 as game_center
import wnba_pra_player_intelligence_v2_step4 as player_intelligence


MODEL_VERSION = "WNBA PRA NAVIGATION V2 • STEP 5 PERFORMANCE + LAZY TRANSITIONS"
SESSION_TTL_SECONDS = 60
MAX_HISTORY_ENTRIES = 12

SESSION_SLATE_PAYLOAD = "ks_wnba_nav_v2_step5_slate_payload"
SESSION_GAME_PAYLOAD = "ks_wnba_nav_v2_step5_game_payload"
SESSION_CONSUMER_CACHE = "ks_wnba_nav_v2_step5_consumer_cache"
SESSION_HISTORY_CACHE = "ks_wnba_nav_v2_step5_history_cache"
SESSION_PERF = "ks_wnba_nav_v2_step5_perf"

_FROZEN_SLATE_LOADER = slate.load_slate
_FROZEN_GAME_LOADER = game_center.load_game_center
_FROZEN_PLAYER_LOADER = player_intelligence.load_player_intelligence

PERFORMANCE_CONTRACT = {
    "project": "WNBA Navigation V2",
    "step": "5/7",
    "scope": "performance_lazy_loading_and_transport_only",
    "frozen_steps_1_through_4_modified": False,
    "native_on_click_single_rerun": True,
    "explicit_st_rerun_added": False,
    "same_session_response_reuse": True,
    "consumer_cache_identity": "global_board_snapshot",
    "history_cache_identity": "player_id",
    "session_cache_ttl_seconds": SESSION_TTL_SECONDS,
    "speculative_prefetch": False,
    "background_prefetch": False,
    "prefetch_only_after_explicit_selection": True,
    "prefetch_targets_per_click_max": 1,
    "slate_prefetches_game_center": False,
    "game_center_prefetches_player_before_selection": False,
    "page3_heavy_model_prefetch": False,
    "streamlit_projection_runs_added": 0,
    "streamlit_sportsbook_calls_added": 0,
    "streamlit_monte_carlo_runs_added": 0,
    "projection_math_changed": False,
    "market_math_changed": False,
    "sportsbook_projection_influence": 0.0,
}


def _now() -> float:
    return time.time()


def _perf() -> dict[str, Any]:
    value = st.session_state.get(SESSION_PERF)
    if not isinstance(value, dict):
        value = {}
        st.session_state[SESSION_PERF] = value
    return value


def _record(**values: Any) -> None:
    current = dict(_perf())
    current.update(values)
    st.session_state[SESSION_PERF] = current


def _fresh_entry(entry: Any) -> Any | None:
    if not isinstance(entry, Mapping):
        return None
    try:
        age = _now() - float(entry.get("ts") or 0.0)
    except Exception:
        return None
    if age < 0 or age > SESSION_TTL_SECONDS:
        return None
    return copy.deepcopy(entry.get("value"))


def _cache_consumer(value: Any) -> None:
    if isinstance(value, Mapping):
        st.session_state[SESSION_CONSUMER_CACHE] = {
            "ts": _now(),
            "value": copy.deepcopy(dict(value)),
        }


def _cached_consumer() -> dict[str, Any] | None:
    value = _fresh_entry(st.session_state.get(SESSION_CONSUMER_CACHE))
    return dict(value) if isinstance(value, Mapping) else None


def _history_store() -> dict[str, Any]:
    value = st.session_state.get(SESSION_HISTORY_CACHE)
    if not isinstance(value, dict):
        value = {}
        st.session_state[SESSION_HISTORY_CACHE] = value
    return value


def _cached_history(player_id: int) -> dict[str, Any] | None:
    store = _history_store()
    value = _fresh_entry(store.get(str(int(player_id))))
    if value is None:
        store.pop(str(int(player_id)), None)
        st.session_state[SESSION_HISTORY_CACHE] = store
        return None
    return dict(value) if isinstance(value, Mapping) else None


def _cache_history(player_id: int, value: Any) -> None:
    if not isinstance(value, Mapping):
        return
    store = _history_store()
    store[str(int(player_id))] = {
        "ts": _now(),
        "value": copy.deepcopy(dict(value)),
    }
    if len(store) > MAX_HISTORY_ENTRIES:
        ordered = sorted(
            store.items(),
            key=lambda item: float((item[1] or {}).get("ts") or 0.0),
            reverse=True,
        )
        store = dict(ordered[:MAX_HISTORY_ENTRIES])
    st.session_state[SESSION_HISTORY_CACHE] = store


def load_player_intelligence_same_session(game_id: str, player_id: int) -> dict[str, Any]:
    """Reuse exact Step-4 payload pieces without changing their meaning.

    Cold pair: use the frozen Step-4 cached/parallel loader.
    Consumer hit + new player: fetch only that player's history.
    History hit + missing consumer: fetch only the consumer.
    Both hit: zero hosted reads.
    """
    pid = int(player_id)
    consumer = _cached_consumer()
    history = _cached_history(pid)
    consumer_hit = consumer is not None
    history_hit = history is not None
    consumer_error = ""
    history_error = ""
    cold_pair_used = False
    direct_reads = 0

    if consumer is None and history is None:
        cold_pair_used = True
        payload = _FROZEN_PLAYER_LOADER(str(game_id), pid)
        maybe_consumer = payload.get("consumer") if isinstance(payload, Mapping) else None
        maybe_history = payload.get("history") if isinstance(payload, Mapping) else None
        consumer_error = str((payload or {}).get("consumer_error") or "") if isinstance(payload, Mapping) else ""
        history_error = str((payload or {}).get("history_error") or "") if isinstance(payload, Mapping) else ""
        if isinstance(maybe_consumer, Mapping):
            consumer = dict(maybe_consumer)
            _cache_consumer(consumer)
        if isinstance(maybe_history, Mapping):
            history = dict(maybe_history)
            _cache_history(pid, history)
    else:
        if consumer is None:
            direct_reads += 1
            try:
                consumer = player_intelligence._read_consumer()
                _cache_consumer(consumer)
            except Exception as exc:
                consumer_error = type(exc).__name__
                consumer = None
        if history is None:
            direct_reads += 1
            try:
                history = player_intelligence._read_history(pid)
                _cache_history(pid, history)
            except Exception as exc:
                history_error = type(exc).__name__
                history = None

    _record(
        player_loader="same_session_split_reuse",
        consumer_session_hit=consumer_hit,
        history_session_hit=history_hit,
        cold_pair_loader_used=cold_pair_used,
        direct_network_reads_this_call=direct_reads,
        duplicate_consumer_read_suppressed=bool(consumer_hit and not history_hit),
    )
    return {
        "game_id": str(game_id),
        "player_id": pid,
        "consumer": consumer,
        "history": history,
        "consumer_error": consumer_error,
        "history_error": history_error,
        "network_reads": 0 if consumer_hit and history_hit else (direct_reads if not cold_pair_used else 2),
        "projection_runs": 0,
        "sportsbook_calls": 0,
        "qualification_runs": 0,
        "ranking_runs": 0,
        "monte_carlo_runs": 0,
        "reuse": {
            "consumer_session_hit": consumer_hit,
            "history_session_hit": history_hit,
            "cold_pair_loader_used": cold_pair_used,
            "direct_network_reads": direct_reads,
        },
    }


def _observe_slate(day_str: str) -> dict[str, Any]:
    payload = _FROZEN_SLATE_LOADER(day_str)
    st.session_state[SESSION_SLATE_PAYLOAD] = copy.deepcopy(payload)
    return payload


def _observe_game_center(
    game_id: str,
    game_date: str,
    away_id: int,
    home_id: int,
    away_team: str,
    home_team: str,
) -> dict[str, Any]:
    payload = _FROZEN_GAME_LOADER(
        game_id,
        game_date,
        away_id,
        home_id,
        away_team,
        home_team,
    )
    st.session_state[SESSION_GAME_PAYLOAD] = copy.deepcopy(payload)
    return payload


def _slate_game(game_id: str) -> dict[str, Any] | None:
    payload = st.session_state.get(SESSION_SLATE_PAYLOAD)
    games = payload.get("games") if isinstance(payload, Mapping) else None
    if not isinstance(games, list):
        return None
    for row in games:
        if isinstance(row, Mapping) and str(row.get("game_id") or "") == str(game_id):
            return dict(row)
    return None


def _game_player(game_id: str, player_id: str) -> dict[str, Any] | None:
    payload = st.session_state.get(SESSION_GAME_PAYLOAD)
    if not isinstance(payload, Mapping) or str(payload.get("game_id") or "") != str(game_id):
        return None
    teams = payload.get("teams")
    if not isinstance(teams, Mapping):
        return None
    for rows in teams.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            try:
                pid = int(row.get("player_id"))
            except (TypeError, ValueError):
                continue
            if str(pid) == str(player_id):
                return dict(row)
    return None


def _prefetch_game(game: Mapping[str, Any]) -> str:
    try:
        args = game_center._game_key(game)
        _FROZEN_GAME_LOADER(*args)
        return "green"
    except Exception as exc:
        return f"deferred:{type(exc).__name__}"


def _prefetch_player(game_id: str, player_id: int) -> str:
    try:
        load_player_intelligence_same_session(game_id, int(player_id))
        return "green"
    except Exception as exc:
        return f"deferred:{type(exc).__name__}"


def _open_game_once(game: Mapping[str, Any]) -> None:
    snapshot = dict(game)
    game_id = str(snapshot.get("game_id") or "")
    if not game_id:
        _record(last_transition="slate_to_game", transition_status="missing_game_id")
        return
    st.session_state[slate.SESSION_SELECTED_GAME] = snapshot
    prefetch = _prefetch_game(snapshot)
    navigation.go_to_game(game_id)
    _record(
        last_transition="slate_to_game",
        transition_transport="native_on_click_single_rerun",
        prefetch_target="selected_game_only",
        prefetch_status=prefetch,
        explicit_rerun=False,
    )


def _open_player_once(game_id: str, player: Mapping[str, Any]) -> None:
    snapshot = dict(player)
    try:
        player_id = int(snapshot.get("player_id"))
    except (TypeError, ValueError):
        _record(last_transition="game_to_player", transition_status="missing_player_id")
        return
    st.session_state[game_center.SESSION_SELECTED_PLAYER] = snapshot
    prefetch = _prefetch_player(str(game_id), player_id)
    navigation.go_to_player(str(game_id), str(player_id))
    _record(
        last_transition="game_to_player",
        transition_transport="native_on_click_single_rerun",
        prefetch_target="selected_player_only",
        prefetch_status=prefetch,
        explicit_rerun=False,
    )


def _back_to_slate_once() -> None:
    navigation.go_to_slate()
    _record(
        last_transition="game_to_slate",
        transition_transport="native_on_click_single_rerun",
        explicit_rerun=False,
    )


def _back_to_game_once(game_id: str) -> None:
    navigation.go_to_game(game_id)
    _record(
        last_transition="player_to_game",
        transition_transport="native_on_click_single_rerun",
        explicit_rerun=False,
    )


def _button_callback(key: str) -> Callable[[], None] | None:
    if key.startswith("wnba_nav_v2_step2_open_"):
        game_id = key.removeprefix("wnba_nav_v2_step2_open_")
        game = _slate_game(game_id)
        return partial(_open_game_once, game) if game is not None else None

    if key.startswith("wnba_nav_v2_step3_player_"):
        suffix = key.removeprefix("wnba_nav_v2_step3_player_")
        if "_" not in suffix:
            return None
        game_id, player_id = suffix.rsplit("_", 1)
        player = _game_player(game_id, player_id)
        return partial(_open_player_once, game_id, player) if player is not None else None

    if key in {
        "wnba_nav_v2_step3_back_slate",
        "wnba_nav_v2_step3_missing_game_back",
        "wnba_nav_v2_step3_mismatch_back",
    }:
        return _back_to_slate_once

    if key in {
        "wnba_nav_v2_step4_back_game",
        "wnba_nav_v2_step4_missing_back",
    }:
        state = navigation.current_state()
        return partial(_back_to_game_once, state.game_id)

    return None


def _performance_button(
    original: Callable[..., Any],
    label: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    key = str(kwargs.get("key") or "")
    callback = _button_callback(key)
    if callback is not None and kwargs.get("on_click") is None:
        kwargs["on_click"] = callback
        _record(
            last_registered_navigation_key=key,
            navigation_callback_registered=True,
        )
    return original(label, *args, **kwargs)


def _render_marker(state: navigation.NavigationState) -> None:
    st.markdown(
        '<span data-wnba-nav-v2-step5="performance" '
        f'data-wnba-nav-page="{state.page}" '
        'data-single-rerun="true" '
        'data-speculative-prefetch="false" '
        'data-same-session-reuse="true" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def render_step5_route() -> dict[str, Any]:
    state = navigation.current_state()
    _render_marker(state)

    original_button = st.button
    original_slate_loader = slate.load_slate
    original_game_loader = game_center.load_game_center
    original_player_loader = player_intelligence.load_player_intelligence

    st.button = partial(_performance_button, original_button)
    try:
        if state.page == navigation.PAGE_SLATE:
            slate.load_slate = _observe_slate
            return slate.render_slate_page()

        if state.page == navigation.PAGE_GAME:
            game_center.load_game_center = _observe_game_center
            return game_center.render_game_center(state)

        player_intelligence.load_player_intelligence = load_player_intelligence_same_session
        return player_intelligence.render_player_intelligence(state)
    finally:
        st.button = original_button
        slate.load_slate = original_slate_loader
        game_center.load_game_center = original_game_loader
        player_intelligence.load_player_intelligence = original_player_loader


__all__ = [
    "MAX_HISTORY_ENTRIES",
    "MODEL_VERSION",
    "PERFORMANCE_CONTRACT",
    "SESSION_PERF",
    "SESSION_TTL_SECONDS",
    "load_player_intelligence_same_session",
    "render_step5_route",
]
