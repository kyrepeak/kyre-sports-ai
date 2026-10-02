"""WNBA PRA Speed V3 Step 9 — runtime compatibility + true-cold handoff.

This Step-9-only overlay preserves every frozen WNBA Navigation V2 / PRA Speed
V3 artifact. It provides two compatibility repairs over the frozen Step-8
router:

1) remove duplicate (team, player_id) Game Center rows before Streamlit creates
   player buttons, preventing duplicate element keys;
2) retain the exact full Step-7 background precompute response in-process and
   hand it directly to the first Player cold-open when available. The foreground
   may bounded-join the already-running Step-7 future, but it never starts a
   second precompute and the unchanged Step-4 loader remains the fallback.

Projection values, model math, market math, provider semantics, and sportsbook
influence are unchanged.
"""
from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError
from copy import deepcopy
from threading import Lock
from time import perf_counter, sleep
from typing import Any, Mapping

import streamlit_memory_lazy_router_wnba_pra_speed_v3_step8 as frozen_parent
import wnba_pra_game_center_v2_step3 as game_center
import wnba_pra_speed_v3_step4_cache as step4_cache
import wnba_pra_speed_v3_step7_precompute as step7_precompute


MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA PRA SPEED V3 STEP 9 RUNTIME GUARDS"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step8"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

PRECOMPUTE_JOIN_SECONDS = 2.25
PRECOMPUTE_HANDOFF_MAX_AGE_SECONDS = 5.0
_STEP9_BUNDLE_LOCK = Lock()
_STEP9_PRECOMPUTED_BUNDLES: dict[tuple[int, int], dict[str, Any]] = {}
_STEP9_HANDOFF_STATE: dict[str, Any] = {}


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def _dedupe_game_center_payload(payload: Any) -> Any:
    """Suppress duplicate player identities without changing surviving values."""
    if not isinstance(payload, Mapping):
        return payload

    teams_obj = payload.get("teams")
    if not isinstance(teams_obj, Mapping):
        return payload

    clean_payload = dict(payload)
    clean_teams: dict[str, list[Any]] = {}
    suppressed = 0

    for team_key, rows_obj in teams_obj.items():
        rows = list(rows_obj or []) if isinstance(rows_obj, (list, tuple)) else []
        seen_player_ids: set[int] = set()
        clean_rows: list[Any] = []

        for row in rows:
            if not isinstance(row, Mapping):
                clean_rows.append(row)
                continue

            pid = game_center._integer(row.get("player_id"))
            if pid is not None:
                if pid in seen_player_ids:
                    suppressed += 1
                    continue
                seen_player_ids.add(pid)

            clean_rows.append(dict(row))

        clean_teams[str(team_key)] = clean_rows

    clean_payload["teams"] = clean_teams
    clean_payload["players"] = sum(len(rows) for rows in clean_teams.values())
    clean_payload["duplicate_player_rows_suppressed"] = suppressed
    clean_payload["duplicate_key_guard_active"] = True
    return clean_payload


def _bundle_key(player_id: int) -> tuple[int, int]:
    return int(player_id), int(step7_precompute.SUPPORTED_SEASON)


def _store_precomputed_outer(player_id: int, body: Mapping[str, Any]) -> None:
    with _STEP9_BUNDLE_LOCK:
        _STEP9_PRECOMPUTED_BUNDLES[_bundle_key(player_id)] = {
            "body": deepcopy(dict(body)),
            "stored_at": step7_precompute.monotonic(),
        }


def _take_precomputed_outer(player_id: int) -> dict[str, Any] | None:
    """Consume one fresh handoff body; never extend the frozen server cache."""
    with _STEP9_BUNDLE_LOCK:
        entry = _STEP9_PRECOMPUTED_BUNDLES.pop(_bundle_key(player_id), None)
    if not isinstance(entry, Mapping):
        return None
    body = entry.get("body")
    try:
        age_seconds = max(
            0.0,
            step7_precompute.monotonic() - float(entry.get("stored_at") or 0.0),
        )
    except (TypeError, ValueError):
        return None
    if age_seconds > PRECOMPUTE_HANDOFF_MAX_AGE_SECONDS:
        return None
    return deepcopy(body) if isinstance(body, Mapping) else None


def _capture_precompute_bundle(player_id: int) -> dict[str, Any]:
    """Preserve Step-7 behavior while retaining its already-fetched full body."""
    pid = int(player_id)
    started = perf_counter()
    status = "error"
    cache_hit = False
    error = ""
    invalid_bundle_retries = 0

    try:
        client = step7_precompute.KyreWNBAAPIClient(
            timeout_seconds=step7_precompute.API_TIMEOUT_SECONDS,
            attempts=step7_precompute.API_ATTEMPTS,
        )
        body = client.get_json(
            f"/api/v1/wnba/players/{pid}/pra-detail-cached",
            params={"season": step7_precompute.SUPPORTED_SEASON},
        )
        if not step7_precompute._validate_warmed_payload(body, player_id=pid):
            invalid_bundle_retries = 1
            sleep(step7_precompute.INVALID_BUNDLE_RETRY_DELAY_SECONDS)
            body = client.get_json(
                f"/api/v1/wnba/players/{pid}/pra-detail-cached",
                params={"season": step7_precompute.SUPPORTED_SEASON},
            )
        if not step7_precompute._validate_warmed_payload(body, player_id=pid):
            raise ValueError(
                "Step-9 precompute handoff received an invalid Step-4 bundle "
                "after the one frozen validation retry."
            )

        cache = body.get("cache")
        cache = dict(cache) if isinstance(cache, Mapping) else {}
        cache_hit = bool(cache.get("hit"))
        _store_precomputed_outer(pid, body)
        status = "green"
    except Exception as exc:
        error = type(exc).__name__

    result = {
        "player_id": pid,
        "status": status,
        "cache_hit": cache_hit,
        "invalid_bundle_retries": invalid_bundle_retries,
        "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
        "error": error,
        "finished_at": step7_precompute.monotonic(),
    }
    key = _bundle_key(pid)
    with step7_precompute._STATE_LOCK:
        step7_precompute._RESULTS[key] = dict(result)
        step7_precompute._FUTURES.pop(key, None)
    return result


def _future_for_player(player_id: int):
    key = _bundle_key(player_id)
    with step7_precompute._STATE_LOCK:
        return step7_precompute._FUTURES.get(key)


def _join_precompute(player_id: int) -> tuple[dict[str, Any] | None, float, bool]:
    """Bounded-join the one existing Step-7 future; never launch a new one."""
    pid = int(player_id)
    outer = _take_precomputed_outer(pid)
    if outer is not None:
        return outer, 0.0, False

    future = _future_for_player(pid)
    if future is None:
        return None, 0.0, False

    started = perf_counter()
    joined = False
    try:
        if not future.done():
            joined = True
            future.result(timeout=PRECOMPUTE_JOIN_SECONDS)
        else:
            future.result()
    except FutureTimeoutError:
        pass
    except Exception:
        pass
    waited_ms = (perf_counter() - started) * 1000.0
    return _take_precomputed_outer(pid), waited_ms, joined


def _pair_from_precomputed_outer(
    game_id: str,
    player_id: int,
    outer: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the exact Step-4 pair without a second Streamlit->API read."""
    pid = int(player_id)
    consumer: dict[str, Any] | None = None
    history: dict[str, Any] | None = None
    consumer_error = ""
    history_error = ""
    cache_hit = False
    generation_ms = 0.0

    cache_meta = outer.get("cache") if isinstance(outer, Mapping) else None
    if isinstance(cache_meta, Mapping):
        cache_hit = bool(cache_meta.get("hit"))
        try:
            generation_ms = float(cache_meta.get("generation_ms") or 0.0)
        except (TypeError, ValueError):
            generation_ms = 0.0

    body = outer.get("bundle") if isinstance(outer, Mapping) else None
    body = body if isinstance(body, Mapping) else {}
    raw_consumer = body.get("consumer")
    raw_history = body.get("history")
    consumer_error = str(body.get("consumer_error") or "")
    history_error = str(body.get("history_error") or "")

    if not consumer_error and isinstance(raw_consumer, Mapping):
        try:
            consumer = step4_cache.normalize_consumer_payload(dict(raw_consumer))
        except Exception as exc:
            consumer_error = type(exc).__name__

    if not history_error and isinstance(raw_history, Mapping):
        history = dict(raw_history)

    step4_cache._record(
        cached_bundle_used=True,
        server_cache_hit=cache_hit,
        cached_bundle_read_ms=0.0,
        server_generation_ms=round(generation_ms, 3),
        streamlit_network_reads=0,
        consumer_present=isinstance(consumer, Mapping),
        history_present=isinstance(history, Mapping),
        consumer_error=consumer_error,
        history_error=history_error,
        bundle_error="",
        player_id=pid,
    )

    return {
        "game_id": str(game_id),
        "player_id": pid,
        "consumer": consumer,
        "history": history,
        "consumer_error": consumer_error,
        "history_error": history_error,
        "network_reads": 0,
        "projection_runs": 0,
        "sportsbook_calls": 0,
        "qualification_runs": 0,
        "ranking_runs": 0,
        "monte_carlo_runs": 0,
        "step4_server_cache_hit": cache_hit,
    }


def _handoff_loader(original_loader, game_id: str, player_id: int) -> dict[str, Any]:
    pid = int(player_id)
    started = perf_counter()
    outer, waited_ms, joined = _join_precompute(pid)
    if outer is not None and step7_precompute._validate_warmed_payload(outer, player_id=pid):
        result = _pair_from_precomputed_outer(str(game_id), pid, outer)
        _STEP9_HANDOFF_STATE.update(
            {
                "player_id": pid,
                "precompute_handoff_used": True,
                "precompute_future_joined": joined,
                "precompute_wait_ms": round(waited_ms, 3),
                "foreground_bundle_network_reads": 0,
                "handoff_total_ms": round((perf_counter() - started) * 1000.0, 3),
            }
        )
        return result

    result = original_loader(str(game_id), pid)
    _STEP9_HANDOFF_STATE.update(
        {
            "player_id": pid,
            "precompute_handoff_used": False,
            "precompute_future_joined": joined,
            "precompute_wait_ms": round(waited_ms, 3),
            "foreground_bundle_network_reads": 1,
            "handoff_total_ms": round((perf_counter() - started) * 1000.0, 3),
        }
    )
    return result


def render_app() -> Any:
    """Render frozen Step-8 with duplicate-key and precompute-handoff guards."""
    original_game_loader = game_center.load_game_center
    original_warm_one = step7_precompute._warm_one
    original_bundle_loader = step4_cache.load_cached_bundle_pair

    def guarded_game_loader(*args: Any, **kwargs: Any) -> Any:
        return _dedupe_game_center_payload(original_game_loader(*args, **kwargs))

    def handoff_bundle_loader(game_id: str, player_id: int) -> dict[str, Any]:
        return _handoff_loader(original_bundle_loader, game_id, player_id)

    if hasattr(original_game_loader, "clear"):
        guarded_game_loader.clear = original_game_loader.clear  # type: ignore[attr-defined]

    game_center.load_game_center = guarded_game_loader
    step7_precompute._warm_one = _capture_precompute_bundle
    step4_cache.load_cached_bundle_pair = handoff_bundle_loader
    try:
        return frozen_parent.render_app()
    finally:
        game_center.load_game_center = original_game_loader
        step7_precompute._warm_one = original_warm_one
        step4_cache.load_cached_bundle_pair = original_bundle_loader


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "PRECOMPUTE_HANDOFF_MAX_AGE_SECONDS",
    "PRECOMPUTE_JOIN_SECONDS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_capture_precompute_bundle",
    "_dedupe_game_center_payload",
    "_handoff_loader",
    "_join_precompute",
    "_pair_from_precomputed_outer",
    "record_bootstrap_import_ms",
    "render_app",
]
