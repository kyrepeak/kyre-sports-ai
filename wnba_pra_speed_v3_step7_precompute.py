"""WNBA PRA Speed V3 Step 7 — non-blocking active-player bundle precompute.

Step 7 warms the already-frozen Step-4 finished PRA bundle cache for every
currently tappable player in the selected WNBA Game Center. It starts only
after the frozen Game Center has produced verified player IDs and never blocks
the Streamlit render or a navigation callback.

No basketball output is recomputed in Streamlit and no model, projection,
market, ranking, qualification, Monte Carlo, sportsbook, or navigation
semantics are changed.
"""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from html import escape
from threading import Lock
from time import monotonic, perf_counter
from typing import Any, Mapping

import streamlit as st

import wnba_pra_navigation_v2_step1 as navigation
import wnba_pra_performance_v2_step5 as performance
from wnba_api_client_v1 import KyreWNBAAPIClient, SUPPORTED_SEASON

MODEL_VERSION = "WNBA PRA SPEED V3 • STEP 7 ACTIVE PLAYER BUNDLE PRECOMPUTE"
EXPECTED_DATA_TYPE = "wnba_pra_speed_v3_step4_cached_detail_bundle"
EXPECTED_SCHEMA_VERSION = "wnba_pra_speed_v3_step4_cached_detail_bundle_v1"

MAX_WORKERS = 2
SCHEDULE_DEDUPE_SECONDS = 45.0
API_TIMEOUT_SECONDS = 5.0
API_ATTEMPTS = 2
SESSION_PERF = "ks_wnba_pra_speed_v3_step7_perf"

PRECOMPUTE_CONTRACT = {
    "project": "WNBA PRA Speed V3",
    "step": "7/9",
    "scope": "precompute_finished_pra_bundles_for_currently_tappable_active_players",
    "source": "frozen_selected_game_center_player_ids",
    "target_endpoint": "/api/v1/wnba/players/{player_id}/pra-detail-cached",
    "background": True,
    "navigation_callback_blocking": False,
    "max_workers": MAX_WORKERS,
    "foreground_headroom_reserved": True,
    "precompute_order": "game_center_display_order",
    "per_player_transport_attempts": API_ATTEMPTS,
    "identity_valid_incomplete_bundle_is_error": False,
    "identity_valid_incomplete_bundle_fallback": "frozen_true_cold_path",
    "schedule_dedupe_seconds": SCHEDULE_DEDUPE_SECONDS,
    "warm_same_session_target_seconds_max": 0.75,
    "precomputed_cold_player_target_seconds_max": 1.5,
    "true_cold_pra_target_seconds_max": 2.5,
    "frozen_speed_v3_steps_1_6_modified": False,
    "projection_math_changed": False,
    "market_math_changed": False,
    "ranking_changed": False,
    "qualification_changed": False,
    "monte_carlo_changed": False,
    "sportsbook_projection_influence": 0.0,
}

_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="wnba-pra-step7")
_STATE_LOCK = Lock()
_LAST_SCHEDULED: dict[tuple[int, int], float] = {}
_FUTURES: dict[tuple[int, int], Future] = {}
_RESULTS: dict[tuple[int, int], dict[str, Any]] = {}


def _valid_player_id(value: Any) -> int | None:
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def active_player_ids(payload: Any) -> list[int]:
    """Return unique verified player IDs in frozen Game Center display order."""
    if not isinstance(payload, Mapping):
        return []
    teams = payload.get("teams")
    if not isinstance(teams, Mapping):
        return []
    result: list[int] = []
    seen: set[int] = set()
    for rows in teams.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            pid = _valid_player_id(row.get("player_id"))
            if pid is None or pid in seen:
                continue
            seen.add(pid)
            result.append(pid)
    return result


def _identity_valid_warmed_payload(body: Any, *, player_id: int) -> bool:
    """Validate the immutable Step-4 envelope without requiring cache completeness."""
    if not isinstance(body, Mapping):
        return False
    try:
        payload_pid = int(body.get("player_id") or 0)
        season = int(body.get("season") or 0)
    except (TypeError, ValueError):
        return False
    bundle = body.get("bundle")
    if not isinstance(bundle, Mapping):
        return False
    try:
        bundle_pid = int(bundle.get("player_id") or 0)
        bundle_season = int(bundle.get("season") or 0)
    except (TypeError, ValueError):
        return False
    return (
        body.get("data_type") == EXPECTED_DATA_TYPE
        and body.get("schema_version") == EXPECTED_SCHEMA_VERSION
        and payload_pid == int(player_id)
        and season == int(SUPPORTED_SEASON)
        and bundle_pid == int(player_id)
        and bundle_season == int(SUPPORTED_SEASON)
    )


def _validate_warmed_payload(body: Any, *, player_id: int) -> bool:
    """Return True only when frozen Step 4 considers the bundle cache-complete."""
    if not _identity_valid_warmed_payload(body, player_id=player_id):
        return False
    bundle = body.get("bundle")
    return (
        isinstance(bundle.get("consumer"), Mapping)
        and isinstance(bundle.get("history"), Mapping)
        and not str(bundle.get("consumer_error") or "")
        and not str(bundle.get("history_error") or "")
    )


def _warm_one(player_id: int) -> dict[str, Any]:
    pid = int(player_id)
    started = perf_counter()
    status = "error"
    cache_hit = False
    error = ""
    try:
        client = KyreWNBAAPIClient(
            timeout_seconds=API_TIMEOUT_SECONDS,
            attempts=API_ATTEMPTS,
        )
        body = client.get_json(
            f"/api/v1/wnba/players/{pid}/pra-detail-cached",
            params={"season": SUPPORTED_SEASON},
        )
        if not _identity_valid_warmed_payload(body, player_id=pid):
            raise ValueError("Step-7 precompute received an invalid Step-4 identity envelope.")
        cache = body.get("cache")
        cache = dict(cache) if isinstance(cache, Mapping) else {}
        cache_hit = bool(cache.get("hit"))
        if _validate_warmed_payload(body, player_id=pid):
            status = "green"
        else:
            # Frozen Step 4 intentionally does not cache incomplete bundles.
            # This is a valid fallback state, not a transport/schema failure.
            status = "incomplete"
    except Exception as exc:
        error = type(exc).__name__
    elapsed_ms = (perf_counter() - started) * 1000.0
    result = {
        "player_id": pid,
        "status": status,
        "cache_hit": cache_hit,
        "elapsed_ms": round(elapsed_ms, 3),
        "error": error,
        "finished_at": monotonic(),
    }
    key = (pid, int(SUPPORTED_SEASON))
    with _STATE_LOCK:
        _RESULTS[key] = dict(result)
        _FUTURES.pop(key, None)
    return result


def schedule_precompute(payload: Any) -> dict[str, Any]:
    """Schedule non-blocking cache warmers for the current selected game's players."""
    player_ids = active_player_ids(payload)
    now = monotonic()
    scheduled = 0
    deduped = 0
    already_running = 0

    with _STATE_LOCK:
        for pid in player_ids:
            key = (int(pid), int(SUPPORTED_SEASON))
            current = _FUTURES.get(key)
            if current is not None and not current.done():
                already_running += 1
                continue
            last = float(_LAST_SCHEDULED.get(key) or 0.0)
            if last > 0.0 and (now - last) < SCHEDULE_DEDUPE_SECONDS:
                deduped += 1
                continue
            _LAST_SCHEDULED[key] = now
            _FUTURES[key] = _EXECUTOR.submit(_warm_one, int(pid))
            scheduled += 1

    return {
        "target_players": len(player_ids),
        "scheduled": scheduled,
        "deduped": deduped,
        "already_running": already_running,
        "background": True,
        "max_workers": MAX_WORKERS,
    }


def precompute_snapshot(player_ids: list[int] | None = None) -> dict[str, Any]:
    ids = list(player_ids or [])
    keys = [(int(pid), int(SUPPORTED_SEASON)) for pid in ids]
    with _STATE_LOCK:
        results = [dict(_RESULTS[k]) for k in keys if k in _RESULTS]
        running = sum(
            1
            for k in keys
            if k in _FUTURES and not _FUTURES[k].done()
        )
    green = sum(1 for row in results if row.get("status") == "green")
    incomplete = sum(1 for row in results if row.get("status") == "incomplete")
    errors = sum(
        1
        for row in results
        if row.get("status") not in {"green", "incomplete"}
    )
    return {
        "targets": len(ids),
        "completed": len(results),
        "green": green,
        "incomplete": incomplete,
        "errors": errors,
        "running": running,
    }


def _record_session(**values: Any) -> None:
    current = st.session_state.get(SESSION_PERF)
    current = dict(current) if isinstance(current, Mapping) else {}
    current.update(values)
    st.session_state[SESSION_PERF] = current


def schedule_from_current_game() -> dict[str, Any]:
    payload = st.session_state.get(performance.SESSION_GAME_PAYLOAD)
    player_ids = active_player_ids(payload)
    scheduled = schedule_precompute(payload)
    snapshot = precompute_snapshot(player_ids)
    state = {
        **scheduled,
        **snapshot,
        "player_ids": player_ids,
    }
    _record_session(**state)
    return state


def _render_marker(state: navigation.NavigationState) -> None:
    perf = st.session_state.get(SESSION_PERF)
    perf = dict(perf) if isinstance(perf, Mapping) else {}
    player_ids = [int(pid) for pid in perf.get("player_ids", []) if _valid_player_id(pid)]
    snap = precompute_snapshot(player_ids)
    if player_ids:
        _record_session(**snap)
        perf.update(snap)

    st.markdown(
        '<span data-wnba-pra-speed-v3-step7="active-player-precompute" '
        f'data-page="{escape(state.page, quote=True)}" '
        f'data-target-players="{int(perf.get("target_players") or perf.get("targets") or 0)}" '
        f'data-scheduled="{int(perf.get("scheduled") or 0)}" '
        f'data-completed="{int(perf.get("completed") or 0)}" '
        f'data-green="{int(perf.get("green") or 0)}" '
        f'data-incomplete="{int(perf.get("incomplete") or 0)}" '
        f'data-errors="{int(perf.get("errors") or 0)}" '
        f'data-running="{int(perf.get("running") or 0)}" '
        'data-background="true" '
        f'data-max-workers="{MAX_WORKERS}" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def render_step7_route(frozen_renderer) -> Any:
    """Render frozen Step 6, then queue verified Game Center players non-blockingly."""
    result = frozen_renderer()
    state = navigation.current_state()
    if state.page == navigation.PAGE_GAME:
        schedule_from_current_game()
    _render_marker(state)
    return result


__all__ = [
    "MAX_WORKERS",
    "MODEL_VERSION",
    "PRECOMPUTE_CONTRACT",
    "SCHEDULE_DEDUPE_SECONDS",
    "SESSION_PERF",
    "active_player_ids",
    "precompute_snapshot",
    "render_step7_route",
    "schedule_precompute",
    "schedule_from_current_game",
]
