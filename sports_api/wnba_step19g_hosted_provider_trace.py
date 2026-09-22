"""WNBA Step 19G: read-only hosted provider trace.

This compatibility diagnostic wraps the already-frozen Step12B live-runtime call
and records only a small sanitized summary of the most recent provider discovery.
It returns the original Step12B object unchanged, so controller state, hashes,
projection math, rankings, persistence, scheduler behavior, and wagering policy
are untouched.

The purpose is to distinguish a hosted-network/provider failure from a scheduler
binding failure when GitHub read-only certification succeeds but the Render
always-on process reports ``provider_transient_not_ready``.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import threading
from typing import Any, Callable

from sports_api import wnba_step11_draftkings_provider as draftkings
from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step19f_draftkings_identity as step19f

SOURCE = "Kyre Sports API WNBA Step19G hosted provider trace"
MODEL_VERSION = "wnba_step19g_hosted_provider_trace_v1"

_ORIGINAL_RUN_STEP12B = step12b.run_step12b_live_runtime_job
_LOCK = threading.RLock()
_LATEST: dict[str, Any] | None = None
_CALL_COUNT = 0
_INSTALLED = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_error(value: object) -> str:
    return " ".join(str(value or "").split())[:300]


def _provider_summary(value: object) -> dict[str, Any]:
    row = value if isinstance(value, Mapping) else {}
    errors: list[dict[str, Any]] = []
    raw_errors = row.get("errors")
    if isinstance(raw_errors, list):
        for item in raw_errors[:5]:
            if not isinstance(item, Mapping):
                continue
            errors.append(
                {
                    "attempt": item.get("attempt"),
                    "error_type": _clean_error(item.get("error_type")),
                    "error_message": _clean_error(item.get("error_message")),
                }
            )
    return {
        "provider": _clean_error(row.get("provider")),
        "attempt_limit": row.get("attempt_limit"),
        "attempts_executed": row.get("attempts_executed"),
        "retryable_failures": row.get("retryable_failures"),
        "record_count": row.get("record_count"),
        "bridge_available": bool(row.get("bridge_content_sha256")),
        "errors": errors,
    }


def _compatibility_status() -> dict[str, bool]:
    return {
        "draftkings_team_identity_patch_active": (
            draftkings._team_identity_key is step19f.team_identity_key_step19f
        ),
        "fanduel_event_date_patch_active": (
            fanduel._event_date is step19f.fanduel_event_date_step19f
        ),
        "fanduel_tab_slug_patch_active": (
            fanduel._relevant_tab_ids is step19f.fanduel_relevant_tab_ids_step19f
        ),
        "fanduel_runner_shape_patch_active": (
            fanduel._runner_side_line is step19f.fanduel_runner_side_line_step19f
        ),
        "fanduel_player_market_patch_active": (
            fanduel._declares_player_market is step19f.fanduel_declares_player_market_step19f
        ),
    }


def _capture_result(result: Mapping[str, Any]) -> None:
    discovery = result.get("provider_discovery")
    discovery = discovery if isinstance(discovery, Mapping) else {}
    step12a_result = result.get("step12a_result")
    step12a_result = step12a_result if isinstance(step12a_result, Mapping) else {}
    tick = step12a_result.get("step11e_tick")
    tick = tick if isinstance(tick, Mapping) else {}
    execution = tick.get("execution")
    execution = execution if isinstance(execution, Mapping) else {}

    snapshot = {
        "captured_at_utc": _now(),
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "status": result.get("status"),
        "health": result.get("health"),
        "slate_date": result.get("slate_date"),
        "cycle_outcome": execution.get("cycle_outcome"),
        "transient_provider_short_circuit": discovery.get("transient_provider_short_circuit") is True,
        "draftkings": _provider_summary(discovery.get("draftkings")),
        "fanduel": _provider_summary(discovery.get("fanduel")),
        "compatibility": _compatibility_status(),
        "exception": None,
        "guardrails": {
            "read_only_trace": True,
            "step12b_result_modified": False,
            "controller_state_modified": False,
            "provider_retry_policy_modified": False,
            "readiness_relaxed": False,
            "projection_logic_modified": False,
            "persistence_modified": False,
            "wagering_enabled": False,
            "secrets_exposed": False,
            "market_records_exposed": False,
        },
    }
    with _LOCK:
        global _LATEST
        _LATEST = snapshot


def _capture_exception(exc: Exception) -> None:
    snapshot = {
        "captured_at_utc": _now(),
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "status": "step12b_exception",
        "health": "error",
        "slate_date": None,
        "cycle_outcome": None,
        "transient_provider_short_circuit": False,
        "draftkings": _provider_summary(None),
        "fanduel": _provider_summary(None),
        "compatibility": _compatibility_status(),
        "exception": {
            "error_type": type(exc).__name__,
            "error_message": _clean_error(exc),
        },
        "guardrails": {
            "read_only_trace": True,
            "step12b_result_modified": False,
            "controller_state_modified": False,
            "provider_retry_policy_modified": False,
            "readiness_relaxed": False,
            "projection_logic_modified": False,
            "persistence_modified": False,
            "wagering_enabled": False,
            "secrets_exposed": False,
            "market_records_exposed": False,
        },
    }
    with _LOCK:
        global _LATEST
        _LATEST = snapshot


def run_step12b_with_hosted_trace(*args: Any, **kwargs: Any) -> dict[str, Any]:
    global _CALL_COUNT
    with _LOCK:
        _CALL_COUNT += 1
    try:
        result = _ORIGINAL_RUN_STEP12B(*args, **kwargs)
    except Exception as exc:
        _capture_exception(exc)
        raise
    if isinstance(result, Mapping):
        _capture_result(result)
    return result


def install_step19g_hosted_provider_trace() -> dict[str, Any]:
    global _INSTALLED
    step19f.install_step19f_draftkings_identity()
    if step12b.run_step12b_live_runtime_job is not run_step12b_with_hosted_trace:
        step12b.run_step12b_live_runtime_job = run_step12b_with_hosted_trace
    _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    return {
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "installed": _INSTALLED,
        "step12b_wrapper_active": step12b.run_step12b_live_runtime_job is run_step12b_with_hosted_trace,
        "compatibility": _compatibility_status(),
        "readiness_relaxed": False,
        "projection_logic_modified": False,
        "controller_state_modified": False,
        "wagering_enabled": False,
    }


def get_step19g_hosted_provider_trace() -> dict[str, Any]:
    with _LOCK:
        latest = deepcopy(_LATEST)
        count = int(_CALL_COUNT)
    return {
        "data_type": "wnba_step19g_hosted_provider_trace",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now(),
        "installed": _INSTALLED,
        "call_count": count,
        "latest": latest,
        "installation": installation_status(),
    }


__all__ = [
    "MODEL_VERSION",
    "SOURCE",
    "get_step19g_hosted_provider_trace",
    "install_step19g_hosted_provider_trace",
    "installation_status",
    "run_step12b_with_hosted_trace",
]
