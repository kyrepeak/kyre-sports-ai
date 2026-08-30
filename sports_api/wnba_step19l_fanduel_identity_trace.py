"""WNBA Step19L: semantics-neutral hosted FanDuel identity flight recorder.

Step19J production observation saw two intermittent
``WNBAStep11FanDuelProviderIdentityError`` cycles on Render while FanDuel HTTP
transport remained 200/valid JSON. Direct GitHub Actions stress did not reproduce
those errors. This layer records only the identity-error category/message and
field-level duplicate-market identity drift for the active FanDuel fetch.

It never changes a market, player, game, line, price, retry, readiness, controller,
projection, persistence, or wagering decision. Every original exception is
re-raised unchanged.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import threading
from typing import Any, Callable

from sports_api import wnba_step11_fanduel_provider as fanduel

SOURCE = "Kyre Sports API WNBA Step19L hosted FanDuel identity flight recorder"
MODEL_VERSION = "wnba_step19l_fanduel_identity_trace_v1"
MAX_ERROR_EVENTS = 24
MAX_DRIFTS_PER_FETCH = 12

_ORIGINAL_MARKET_IDENTITY_SURFACE = fanduel._market_identity_surface
_UPSTREAM_FETCH_STEP11C: Callable[..., Any] | None = None
_INSTALLED = False
_LOCK = threading.RLock()
_ACTIVE_TRACE: ContextVar[dict[str, Any] | None] = ContextVar(
    "wnba_step19l_active_fanduel_identity_trace", default=None
)
_ERROR_EVENTS: list[dict[str, Any]] = []
_FETCH_COUNT = 0
_SUCCESS_COUNT = 0
_IDENTITY_ERROR_COUNT = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: object, limit: int = 360) -> str:
    return " ".join(str(value or "").split())[:limit]


def _error_category(message: str) -> str:
    text = message.casefold()
    checks = (
        ("conflicting_market_identity", "conflicting fanduel market identity"),
        ("conflicting_same_timestamp_payload", "conflicting same-timestamp fanduel market payload"),
        ("conflicting_event_metadata", "conflicting fanduel event metadata"),
        ("player_unmapped", "could not uniquely map fanduel player"),
        ("player_wrong_game_team", "is not on either official game team"),
        ("event_unreconciled", "unreconciled fanduel event"),
        ("game_not_unique", "requires one official wnba game"),
        ("duplicate_same_side", "duplicate same-side fanduel quote"),
        ("pair_capture_mismatch", "over/under pair must share capture timestamp"),
        ("runner_price", "fanduel runner"),
        ("odds_contract", "fanduel odds outside frozen"),
        ("line_contract", "fanduel line outside frozen"),
        ("roster_identity", "official roster"),
        ("event_shape", "fanduel event lacks unique id/two team identities"),
        ("content_event_id", "content page returned event without id"),
    )
    for category, token in checks:
        if token in text:
            return category
    return "other_identity_error"


def _runner_line_shapes(surface: Mapping[str, Any]) -> list[str]:
    rows = surface.get("runners") or []
    if not isinstance(rows, list):
        return []
    return sorted(
        {
            f"{row.get('handicap')!r}|{row.get('line')!r}|{row.get('side')!r}|{row.get('result_type')!r}"
            for row in rows
            if isinstance(row, Mapping)
        }
    )


def _runner_selection_ids(surface: Mapping[str, Any]) -> list[str]:
    rows = surface.get("runners") or []
    if not isinstance(rows, list):
        return []
    return sorted(
        str(row.get("selection_id") or "")
        for row in rows
        if isinstance(row, Mapping)
    )


def market_identity_surface_step19l(market: Mapping[str, Any]) -> dict[str, Any]:
    """Delegate unchanged while recording duplicate-market identity field drift."""
    surface = _ORIGINAL_MARKET_IDENTITY_SURFACE(market)
    trace = _ACTIVE_TRACE.get()
    if trace is None:
        return surface

    market_id = str(surface.get("market_id") or "")
    if not market_id:
        return surface
    seen = trace.setdefault("seen", {})
    previous = seen.get(market_id)
    if isinstance(previous, Mapping) and previous != surface:
        changed = sorted(
            key for key in set(previous) | set(surface)
            if previous.get(key) != surface.get(key)
        )
        drifts = trace.setdefault("drifts", [])
        if len(drifts) < MAX_DRIFTS_PER_FETCH:
            before_lines = _runner_line_shapes(previous)
            after_lines = _runner_line_shapes(surface)
            before_ids = _runner_selection_ids(previous)
            after_ids = _runner_selection_ids(surface)
            drifts.append(
                {
                    "market_id_sha12": hashlib.sha256(market_id.encode()).hexdigest()[:12],
                    "changed_fields": changed,
                    "runner_count_before": len(previous.get("runners") or []),
                    "runner_count_after": len(surface.get("runners") or []),
                    "line_shape_changed": before_lines != after_lines,
                    "selection_ids_changed": before_ids != after_ids,
                }
            )
    seen[market_id] = deepcopy(surface)
    return surface


def _append_error(event: Mapping[str, Any]) -> None:
    with _LOCK:
        _ERROR_EVENTS.append(deepcopy(dict(event)))
        if len(_ERROR_EVENTS) > MAX_ERROR_EVENTS:
            del _ERROR_EVENTS[:-MAX_ERROR_EVENTS]


def fetch_step11c_with_identity_trace(*args: Any, **kwargs: Any) -> Any:
    """Delegate to the installed FanDuel fetch chain and re-raise every error unchanged."""
    upstream = _UPSTREAM_FETCH_STEP11C
    if upstream is None:
        raise RuntimeError("Step19L FanDuel identity trace is not installed.")

    trace: dict[str, Any] = {"seen": {}, "drifts": []}
    token = _ACTIVE_TRACE.set(trace)
    with _LOCK:
        global _FETCH_COUNT
        _FETCH_COUNT += 1
        fetch_number = _FETCH_COUNT
    try:
        result = upstream(*args, **kwargs)
    except fanduel.WNBAStep11FanDuelProviderIdentityError as exc:
        message = _safe_text(exc)
        with _LOCK:
            global _IDENTITY_ERROR_COUNT
            _IDENTITY_ERROR_COUNT += 1
        _append_error(
            {
                "captured_at_utc": _now(),
                "fetch_number": fetch_number,
                "error_type": type(exc).__name__,
                "category": _error_category(message),
                "error_message": message,
                "duplicate_market_drift": deepcopy(trace.get("drifts") or []),
                "payload_logged": False,
                "prices_logged": False,
                "query_logged": False,
            }
        )
        raise
    else:
        with _LOCK:
            global _SUCCESS_COUNT
            _SUCCESS_COUNT += 1
        return result
    finally:
        _ACTIVE_TRACE.reset(token)


def install_step19l_fanduel_identity_trace() -> dict[str, Any]:
    """Install after Step19I/H so the complete certified FanDuel fetch chain is observed."""
    global _INSTALLED, _UPSTREAM_FETCH_STEP11C

    current_surface = fanduel._market_identity_surface
    if current_surface not in {_ORIGINAL_MARKET_IDENTITY_SURFACE, market_identity_surface_step19l}:
        raise RuntimeError("Step19L refuses to replace an unknown FanDuel market identity surface.")

    current_fetch = fanduel.fetch_step11c_fanduel_provider_bridge
    if current_fetch is fetch_step11c_with_identity_trace:
        _INSTALLED = True
        return installation_status()
    if _UPSTREAM_FETCH_STEP11C is not None and current_fetch is not _UPSTREAM_FETCH_STEP11C:
        raise RuntimeError("Step19L refuses to replace an unknown FanDuel fetch wrapper.")

    _UPSTREAM_FETCH_STEP11C = current_fetch
    fanduel._market_identity_surface = market_identity_surface_step19l
    fanduel.fetch_step11c_fanduel_provider_bridge = fetch_step11c_with_identity_trace
    _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    with _LOCK:
        fetches = int(_FETCH_COUNT)
        successes = int(_SUCCESS_COUNT)
        errors = int(_IDENTITY_ERROR_COUNT)
    return {
        "data_type": "wnba_step19l_fanduel_identity_trace_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now(),
        "installed": _INSTALLED,
        "fetch_wrapper_active": (
            fanduel.fetch_step11c_fanduel_provider_bridge is fetch_step11c_with_identity_trace
        ),
        "market_identity_trace_active": (
            fanduel._market_identity_surface is market_identity_surface_step19l
        ),
        "fetch_count": fetches,
        "success_count": successes,
        "identity_error_count": errors,
        "guardrails": {
            "provider_result_modified": False,
            "exception_modified": False,
            "identity_matching_modified": False,
            "game_uniqueness_relaxed": False,
            "player_identity_relaxed": False,
            "market_identity_relaxed": False,
            "line_matching_modified": False,
            "prices_logged": False,
            "payload_logged": False,
            "query_logged": False,
            "readiness_relaxed": False,
            "provider_retry_policy_modified": False,
            "controller_state_modified": False,
            "projection_logic_modified": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


def get_step19l_fanduel_identity_trace() -> dict[str, Any]:
    with _LOCK:
        events = deepcopy(_ERROR_EVENTS)
    return {
        **installation_status(),
        "latest_error": events[-1] if events else None,
        "error_events": events,
    }


def _clear_for_test() -> None:
    with _LOCK:
        global _FETCH_COUNT, _SUCCESS_COUNT, _IDENTITY_ERROR_COUNT
        _ERROR_EVENTS.clear()
        _FETCH_COUNT = 0
        _SUCCESS_COUNT = 0
        _IDENTITY_ERROR_COUNT = 0


__all__ = [
    "MODEL_VERSION",
    "SOURCE",
    "fetch_step11c_with_identity_trace",
    "get_step19l_fanduel_identity_trace",
    "install_step19l_fanduel_identity_trace",
    "installation_status",
    "market_identity_surface_step19l",
]
