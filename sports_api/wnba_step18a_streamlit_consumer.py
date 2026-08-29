"""WNBA Step 18A: read-only Streamlit consumer snapshot contract.

The certified Step-17 runtime computes a compact Step-12C application-facing
board during each successful durable scheduler cycle, but Step-14 intentionally
persists only restart controller state. Step 18A captures that already-computed
board in process memory at the frozen Step-13C success boundary before Step-14C
discards the larger response.

This module never starts a scheduler, opens or writes a database connection,
calls a sportsbook/provider, runs a projection, or runs Monte Carlo. The capture
wrapper returns the original Step-13C response unchanged. Capture failures are
isolated from the certified scheduler cycle and merely leave the consumer
snapshot unavailable.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import threading
from typing import Any

from sports_api import wnba_step13c_reliability_recovery as step13c

SOURCE = "Kyre Sports API WNBA Step 18A Streamlit consumer snapshot"
SCHEMA_VERSION = "wnba_step_18a_streamlit_consumer_v1"
CONSUMER_VERSION = "wnba_step18a_in_memory_latest_board_v1"
BRANCH = "wnba-step18a-streamlit-consumer-contract-20260829"
STEP17D_FROZEN_RUNTIME_SHA = "8448984adc779fb9af7c7a8187b0eaeb67d034c8"

STEP18A_ENABLED_ENV = "WNBA_STEP18A_STREAMLIT_CONSUMER_ENABLED"
DEFAULT_ENABLED = False
STALE_AFTER_SECONDS = 180

_SNAPSHOT_LOCK = threading.RLock()
_LATEST_SNAPSHOT: dict[str, Any] | None = None


class WNBAStep18AConsumerIntegrityError(RuntimeError):
    pass


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step18a_streamlit_consumer_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP18A_ENABLED_ENV))


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _valid_sha256(value: object) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _utc(value: object, label: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise WNBAStep18AConsumerIntegrityError(
                f"Step 18A {label} must be timezone-aware ISO-8601."
            ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WNBAStep18AConsumerIntegrityError(
            f"Step 18A {label} must be timezone-aware ISO-8601."
        )
    return parsed.astimezone(timezone.utc)


def _json_object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WNBAStep18AConsumerIntegrityError(f"Step 18A {label} must be an object.")
    try:
        normalized = json.loads(
            json.dumps(dict(value), sort_keys=True, ensure_ascii=False, allow_nan=False)
        )
    except (TypeError, ValueError) as exc:
        raise WNBAStep18AConsumerIntegrityError(
            f"Step 18A {label} must be strict JSON-compatible."
        ) from exc
    if not isinstance(normalized, dict):
        raise WNBAStep18AConsumerIntegrityError(f"Step 18A {label} must normalize to an object.")
    return normalized


def _verify_step13c_response(response: Mapping[str, Any]) -> None:
    if not isinstance(response, Mapping):
        raise WNBAStep18AConsumerIntegrityError("Step 18A requires a Step-13C response object.")
    if response.get("data_type") != "wnba_step13c_reliability_recovery_response":
        raise WNBAStep18AConsumerIntegrityError("Step 18A received the wrong Step-13C data type.")
    if response.get("schema_version") != step13c.SCHEMA_VERSION:
        raise WNBAStep18AConsumerIntegrityError("Step 18A detected Step-13C schema drift.")
    if response.get("status") != "completed":
        raise WNBAStep18AConsumerIntegrityError("Step 18A captures only completed Step-13C cycles.")
    observed = str(response.get("reliability_content_sha256") or "").strip().lower()
    surface = {
        key: deepcopy(value)
        for key, value in response.items()
        if key not in {"generated_at_utc", "reliability_content_sha256"}
    }
    expected = _canonical_hash(surface)
    if not _valid_sha256(observed) or observed != expected:
        raise WNBAStep18AConsumerIntegrityError("Step 18A detected Step-13C content-hash drift.")


def _extract_snapshot(
    response: Mapping[str, Any], *, captured_at_utc: datetime | str | None = None
) -> dict[str, Any]:
    _verify_step13c_response(response)
    supervisor = response.get("latest_supervisor")
    if not isinstance(supervisor, Mapping):
        raise WNBAStep18AConsumerIntegrityError("Step 18A Step-13B supervisor payload is missing.")
    scheduler = supervisor.get("latest_scheduler")
    if not isinstance(scheduler, Mapping):
        raise WNBAStep18AConsumerIntegrityError("Step 18A Step-13A scheduler payload is missing.")
    board = _json_object(scheduler.get("latest_board"), "latest board")
    runtime = _json_object(scheduler.get("latest_runtime"), "latest runtime")
    if not isinstance(board.get("available"), bool):
        raise WNBAStep18AConsumerIntegrityError("Step 18A latest board availability flag is invalid.")
    slate_date = str(scheduler.get("slate_date") or supervisor.get("active_slate_date") or "").strip()
    if not slate_date:
        raise WNBAStep18AConsumerIntegrityError("Step 18A slate date is missing.")
    health = str(scheduler.get("health") or supervisor.get("health") or response.get("health") or "").strip()
    if not health:
        raise WNBAStep18AConsumerIntegrityError("Step 18A scheduler health is missing.")
    captured = (
        _utc(captured_at_utc, "captured_at_utc")
        if captured_at_utc is not None
        else datetime.now(timezone.utc)
    )
    source_generated = _utc(
        scheduler.get("generated_at_utc") or response.get("generated_at_utc"),
        "source generated_at_utc",
    )
    snapshot = {
        "slate_date": slate_date,
        "health": health,
        "board": board,
        "runtime": runtime,
        "source_generated_at_utc": source_generated.isoformat(),
        "captured_at_utc": captured.isoformat(),
        "source_step13c_reliability_content_sha256": str(
            response.get("reliability_content_sha256") or ""
        ).lower(),
        "source_step13a_scheduler_content_sha256": str(
            (supervisor.get("lineage") or {}).get("latest_step13a_scheduler_content_sha256") or ""
        ).lower(),
    }
    snapshot["snapshot_content_sha256"] = _canonical_hash(
        {key: deepcopy(value) for key, value in snapshot.items() if key != "captured_at_utc"}
    )
    return snapshot


def capture_step13c_response(
    response: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    captured_at_utc: datetime | str | None = None,
) -> bool:
    """Capture a consumer board without affecting the scheduler result."""
    if not step18a_streamlit_consumer_enabled(env):
        return False
    try:
        snapshot = _extract_snapshot(response, captured_at_utc=captured_at_utc)
    except Exception:
        return False
    with _SNAPSHOT_LOCK:
        global _LATEST_SNAPSHOT
        _LATEST_SNAPSHOT = snapshot
    return True


def run_step13c_and_capture(
    request: Mapping[str, Any], *, env: Mapping[str, str] | None = None, **kwargs: Any
) -> dict[str, Any]:
    """Delegate to frozen Step 13C, capture its already-computed board, return unchanged."""
    response = step13c.run_step13c_reliability_recovery(request, env=env, **kwargs)
    capture_step13c_response(response, env=env)
    return response


def _empty_board() -> dict[str, Any]:
    return {
        "available": False,
        "reason": "awaiting_first_successful_scheduler_cycle",
        "requested_top_card_count": None,
        "qualified_prop_count": 0,
        "primary_top_cards": [],
        "value_ranking": [],
    }


def build_step18a_consumer_latest(
    *, now_utc: datetime | str | None = None, env: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Return the latest in-memory board using a stable, read-only GET contract."""
    enabled = step18a_streamlit_consumer_enabled(env)
    now = _utc(now_utc, "now_utc") if now_utc is not None else datetime.now(timezone.utc)
    with _SNAPSHOT_LOCK:
        snapshot = deepcopy(_LATEST_SNAPSHOT)

    if not enabled:
        snapshot = None
        reason = "consumer_disabled"
    elif snapshot is None:
        reason = "awaiting_first_successful_scheduler_cycle"
    else:
        reason = "board_ready" if snapshot["board"].get("available") is True else str(
            snapshot["board"].get("reason") or "board_unavailable"
        )

    captured_at = _utc(snapshot["captured_at_utc"], "captured_at_utc") if snapshot else None
    age_seconds = None if captured_at is None else max(0.0, (now - captured_at).total_seconds())
    stale = age_seconds is not None and age_seconds > STALE_AFTER_SECONDS
    board = deepcopy(snapshot["board"]) if snapshot is not None else _empty_board()
    if snapshot is None:
        board["reason"] = reason

    return {
        "data_type": "wnba_step18a_streamlit_consumer_latest",
        "schema_version": SCHEMA_VERSION,
        "consumer_version": CONSUMER_VERSION,
        "source": SOURCE,
        "generated_at_utc": now.isoformat(),
        "enabled": enabled,
        "available": bool(enabled and snapshot is not None and board.get("available") is True),
        "reason": reason,
        "slate_date": None if snapshot is None else snapshot["slate_date"],
        "health": None if snapshot is None else snapshot["health"],
        "snapshot": {
            "captured_at_utc": None if snapshot is None else snapshot["captured_at_utc"],
            "source_generated_at_utc": None if snapshot is None else snapshot["source_generated_at_utc"],
            "age_seconds": None if age_seconds is None else round(age_seconds, 3),
            "stale_after_seconds": STALE_AFTER_SECONDS,
            "stale": bool(stale),
            "snapshot_content_sha256": None if snapshot is None else snapshot["snapshot_content_sha256"],
        },
        "board": board,
        "runtime": {} if snapshot is None else deepcopy(snapshot["runtime"]),
        "lineage": {
            "step17d_frozen_runtime_sha": STEP17D_FROZEN_RUNTIME_SHA,
            "source_step13c_reliability_content_sha256": None if snapshot is None else snapshot[
                "source_step13c_reliability_content_sha256"
            ],
            "source_step13a_scheduler_content_sha256": None if snapshot is None else snapshot[
                "source_step13a_scheduler_content_sha256"
            ],
        },
        "semantics": {
            "read_only_get": True,
            "in_memory_snapshot_only": True,
            "database_connection_opened": False,
            "database_read_performed": False,
            "database_write_performed": False,
            "scheduler_started": False,
            "scheduler_cycle_triggered": False,
            "sportsbook_network_called": False,
            "projection_run": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "database_secret_exposed": False,
            "new_render_service_created": False,
        },
    }


def _clear_snapshot_for_test() -> None:
    with _SNAPSHOT_LOCK:
        global _LATEST_SNAPSHOT
        _LATEST_SNAPSHOT = None


__all__ = [
    "BRANCH",
    "CONSUMER_VERSION",
    "DEFAULT_ENABLED",
    "SCHEMA_VERSION",
    "SOURCE",
    "STALE_AFTER_SECONDS",
    "STEP17D_FROZEN_RUNTIME_SHA",
    "STEP18A_ENABLED_ENV",
    "WNBAStep18AConsumerIntegrityError",
    "build_step18a_consumer_latest",
    "capture_step13c_response",
    "run_step13c_and_capture",
    "step18a_streamlit_consumer_enabled",
]
