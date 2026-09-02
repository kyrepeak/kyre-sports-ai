"""WNBA Step 13C: reliability and bounded recovery over frozen Step 13B.

Step 13B owns foreground lifecycle supervision, Step 13A owns bounded scheduling,
and the frozen Step-11E controller owns refresh cadence and circuit timing.
Step 13C adds a process-local active-run lease, bounded recovery from transport-
level process failures, recovery backoff, and last-known-good restart handoff.

This layer does not reinterpret provider health or retry integrity failures. Only
TimeoutError and ConnectionError are recoverable. All frozen input/integrity
errors and unknown exceptions fail closed. The entire runtime remains shadow-
only, foreground-only, read-only, non-persistent, and non-production. Durable
cross-process leases and restart persistence remain Step 14 work.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, MutableSet
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import threading
import time
from typing import Any

from sports_api import wnba_step13a_bounded_scheduler as step13a
from sports_api import wnba_step13b_runtime_supervisor as step13b

SOURCE = "Kyre Sports API WNBA Step 13C scheduler reliability and recovery"
SCHEMA_VERSION = "wnba_step_13c_reliability_recovery_v1"
REQUEST_SCHEMA_VERSION = "wnba_step_13c_reliability_recovery_request_v1"
MODEL_VERSION = "wnba_step13c_process_local_lease_bounded_transport_recovery_2026_regular_v1"
STEP13B_FROZEN_SHA = "0a0e4381d0a4deac6bbd3741f893214e99afef7b"
STEP13A_FROZEN_SHA = step13b.STEP13A_FROZEN_SHA
STEP12D_FROZEN_SHA = step13b.STEP12D_FROZEN_SHA
STEP13C_RELIABILITY_RECOVERY_ENABLED_ENV = "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED"

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PERSISTENCE_ALLOWED = False
SUPABASE_WRITE_ALLOWED = False
PUBLIC_FASTAPI_ACTIVATION_ALLOWED = False
WAGERING_ALLOWED = False
AUTHENTICATION_ALLOWED = False
COOKIES_ALLOWED = False
BACKGROUND_DAEMON_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
FOREGROUND_RELIABILITY_MANAGER_ALLOWED = True
PROCESS_LOCAL_ACTIVE_RUN_LEASE_ALLOWED = True
DURABLE_DISTRIBUTED_LEASE_ALLOWED = False

MIN_RECOVERY_ATTEMPTS = 1
MAX_RECOVERY_ATTEMPTS = 5
DEFAULT_MAX_RECOVERY_ATTEMPTS = 3
MIN_RECOVERY_BACKOFF_SECONDS = 0
MAX_RECOVERY_BACKOFF_SECONDS = 30
DEFAULT_RECOVERY_BACKOFF_SECONDS = 2
MIN_TOTAL_RECOVERY_SLEEP_SECONDS = 0
MAX_TOTAL_RECOVERY_SLEEP_SECONDS = 120
DEFAULT_MAX_TOTAL_RECOVERY_SLEEP_SECONDS = 30
MAX_SINGLE_RECOVERY_SLEEP_SECONDS = 30
_TIME_TOLERANCE_SECONDS = 0.001

_FORBIDDEN_TRUE_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)

_REQUIRED_TRUE_ENV_KEYS = (
    "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED",
    "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED",
    "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED",
    "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED",
    "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
    "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
    "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
)

_REQUEST_REQUIRED_FIELDS = {
    "data_type",
    "schema_version",
    "supervisor_request",
    "max_recovery_attempts",
    "base_recovery_backoff_seconds",
    "max_total_recovery_sleep_seconds",
    "run_identity_sha256",
}
_REQUEST_OPTIONAL_FIELDS = {"request_content_sha256"}

_ACTIVE_RUN_IDENTITIES: set[str] = set()
_ACTIVE_RUN_IDENTITIES_LOCK = threading.Lock()


class WNBAStep13ReliabilityDisabledError(RuntimeError):
    """Raised when Step 13C or a frozen parent is not safely enabled."""


class WNBAStep13ReliabilityInputError(ValueError):
    """Raised when a Step-13C request is malformed."""


class WNBAStep13ReliabilityIntegrityError(RuntimeError):
    """Raised when frozen parent output, lineage, hash, or lease identity drifts."""


class WNBAStep13DuplicateRunError(RuntimeError):
    """Raised when the same Step-13C run identity is already active in this process."""


class WNBAStep13ReliabilityFatalError(RuntimeError):
    """Raised for a non-recoverable unknown runtime exception."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step13c_reliability_recovery_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP13C_RELIABILITY_RECOVERY_ENABLED_ENV))


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _valid_sha256(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _strict_int(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise WNBAStep13ReliabilityInputError(f"Step 13C {label} must be an integer.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep13ReliabilityInputError(f"Step 13C {label} must be an integer.") from exc
    if isinstance(value, float) and not value.is_integer():
        raise WNBAStep13ReliabilityInputError(f"Step 13C {label} must be an integer.")
    if isinstance(value, str) and str(result) != value.strip():
        raise WNBAStep13ReliabilityInputError(f"Step 13C {label} must be an integer.")
    if not minimum <= result <= maximum:
        raise WNBAStep13ReliabilityInputError(
            f"Step 13C {label} must be from {minimum} through {maximum}."
        )
    return result


def _clock_now(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if not isinstance(value, datetime):
        raise WNBAStep13ReliabilityIntegrityError("Step 13C clock must return datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise WNBAStep13ReliabilityIntegrityError("Step 13C clock must be timezone-aware.")
    return value.astimezone(timezone.utc)


def _supervisor_request_surface(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in request.items()
        if key != "request_content_sha256"
    }


def _verify_supervisor_request(request: Mapping[str, Any]) -> str:
    if not isinstance(request, Mapping):
        raise WNBAStep13ReliabilityInputError("Step 13C supervisor_request must be an object.")
    if request.get("data_type") != "wnba_step13b_runtime_supervisor_request":
        raise WNBAStep13ReliabilityInputError("Step 13C requires a frozen Step-13B request.")
    if request.get("schema_version") != step13b.REQUEST_SCHEMA_VERSION:
        raise WNBAStep13ReliabilityInputError("Step 13C Step-13B request schema drift.")
    observed = str(request.get("request_content_sha256") or "").strip().lower()
    expected = _canonical_hash(_supervisor_request_surface(request))
    if not _valid_sha256(observed) or observed != expected:
        raise WNBAStep13ReliabilityIntegrityError(
            "Step 13C detected Step-13B request content-hash mismatch."
        )
    if request.get("season") != 2026:
        raise WNBAStep13ReliabilityInputError(
            "Step 13C is certified only for the 2026 WNBA Regular Season."
        )
    return observed


def _run_identity(supervisor_request_sha256: str) -> str:
    return _canonical_hash(
        {
            "data_type": "wnba_step13c_process_local_run_identity",
            "step13b_frozen_sha": STEP13B_FROZEN_SHA,
            "supervisor_request_content_sha256": supervisor_request_sha256,
        }
    )


def _request_surface(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in request.items()
        if key != "request_content_sha256"
    }


def build_step13c_request(
    *,
    supervisor_request: Mapping[str, Any],
    max_recovery_attempts: int = DEFAULT_MAX_RECOVERY_ATTEMPTS,
    base_recovery_backoff_seconds: int = DEFAULT_RECOVERY_BACKOFF_SECONDS,
    max_total_recovery_sleep_seconds: int = DEFAULT_MAX_TOTAL_RECOVERY_SLEEP_SECONDS,
) -> dict[str, Any]:
    parent_hash = _verify_supervisor_request(supervisor_request)
    request = {
        "data_type": "wnba_step13c_reliability_recovery_request",
        "schema_version": REQUEST_SCHEMA_VERSION,
        "supervisor_request": deepcopy(dict(supervisor_request)),
        "max_recovery_attempts": _strict_int(
            max_recovery_attempts,
            "max_recovery_attempts",
            MIN_RECOVERY_ATTEMPTS,
            MAX_RECOVERY_ATTEMPTS,
        ),
        "base_recovery_backoff_seconds": _strict_int(
            base_recovery_backoff_seconds,
            "base_recovery_backoff_seconds",
            MIN_RECOVERY_BACKOFF_SECONDS,
            MAX_RECOVERY_BACKOFF_SECONDS,
        ),
        "max_total_recovery_sleep_seconds": _strict_int(
            max_total_recovery_sleep_seconds,
            "max_total_recovery_sleep_seconds",
            MIN_TOTAL_RECOVERY_SLEEP_SECONDS,
            MAX_TOTAL_RECOVERY_SLEEP_SECONDS,
        ),
        "run_identity_sha256": _run_identity(parent_hash),
    }
    request["request_content_sha256"] = _canonical_hash(request)
    return request


def _validate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise WNBAStep13ReliabilityInputError("Step 13C request must be an object.")
    keys = set(request)
    unknown = sorted(keys - _REQUEST_REQUIRED_FIELDS - _REQUEST_OPTIONAL_FIELDS)
    missing = sorted(_REQUEST_REQUIRED_FIELDS - keys)
    if unknown:
        raise WNBAStep13ReliabilityInputError(
            "Unknown Step-13C request fields: " + ", ".join(unknown)
        )
    if missing:
        raise WNBAStep13ReliabilityInputError(
            "Missing Step-13C request fields: " + ", ".join(missing)
        )
    if request.get("data_type") != "wnba_step13c_reliability_recovery_request":
        raise WNBAStep13ReliabilityInputError("Step 13C request data_type drift.")
    if request.get("schema_version") != REQUEST_SCHEMA_VERSION:
        raise WNBAStep13ReliabilityInputError("Step 13C request schema_version drift.")
    parent = request.get("supervisor_request")
    parent_hash = _verify_supervisor_request(parent)
    expected_identity = _run_identity(parent_hash)
    observed_identity = str(request.get("run_identity_sha256") or "").strip().lower()
    if not _valid_sha256(observed_identity) or observed_identity != expected_identity:
        raise WNBAStep13ReliabilityIntegrityError("Step 13C run identity mismatch.")
    observed = str(request.get("request_content_sha256") or "").strip().lower()
    expected = _canonical_hash(_request_surface(request))
    if not _valid_sha256(observed) or observed != expected:
        raise WNBAStep13ReliabilityIntegrityError("Step 13C request content hash mismatch.")
    return {
        "supervisor_request": deepcopy(dict(parent)),
        "supervisor_request_content_sha256": parent_hash,
        "run_identity_sha256": observed_identity,
        "max_recovery_attempts": _strict_int(
            request.get("max_recovery_attempts"),
            "max_recovery_attempts",
            MIN_RECOVERY_ATTEMPTS,
            MAX_RECOVERY_ATTEMPTS,
        ),
        "base_recovery_backoff_seconds": _strict_int(
            request.get("base_recovery_backoff_seconds"),
            "base_recovery_backoff_seconds",
            MIN_RECOVERY_BACKOFF_SECONDS,
            MAX_RECOVERY_BACKOFF_SECONDS,
        ),
        "max_total_recovery_sleep_seconds": _strict_int(
            request.get("max_total_recovery_sleep_seconds"),
            "max_total_recovery_sleep_seconds",
            MIN_TOTAL_RECOVERY_SLEEP_SECONDS,
            MAX_TOTAL_RECOVERY_SLEEP_SECONDS,
        ),
        "request_content_sha256": observed,
    }


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    if not step13c_reliability_recovery_enabled(source):
        raise WNBAStep13ReliabilityDisabledError(
            f"Step 13C requires {STEP13C_RELIABILITY_RECOVERY_ENABLED_ENV}=true."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep13ReliabilityDisabledError(
            "Step 13C refuses production/persistence/write/legacy scheduler switches: "
            + ", ".join(bad)
        )
    missing = [name for name in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(name))]
    if missing:
        raise WNBAStep13ReliabilityDisabledError(
            "Step 13C requires frozen Step-13B/13A/12 runtime gates: " + ", ".join(missing)
        )
    if step13b.STEP13A_FROZEN_SHA != "eaa744ae097a94d5f54c490ab13ca7d66bb725c2":
        raise WNBAStep13ReliabilityIntegrityError("Step 13C frozen Step-13A lineage drift.")
    if step13b.STEP12D_FROZEN_SHA != "48517bac86ee3f55aa4c21d6caba06c41a0a7d60":
        raise WNBAStep13ReliabilityIntegrityError("Step 13C frozen Step-12D lineage drift.")
    if step13a.STEP12D_FROZEN_SHA != step13b.STEP12D_FROZEN_SHA:
        raise WNBAStep13ReliabilityIntegrityError("Step 13C Step-13A/13B parent drift.")
    parent_false = {
        "step13b_default": step13b.DEFAULT_ENABLED,
        "step13b_production": step13b.PRODUCTION_ACTIVATION_ALLOWED,
        "step13b_persistence": step13b.PERSISTENCE_ALLOWED,
        "step13b_supabase": step13b.SUPABASE_WRITE_ALLOWED,
        "step13b_public_api": step13b.PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step13b_wagering": step13b.WAGERING_ALLOWED,
        "step13b_auth": step13b.AUTHENTICATION_ALLOWED,
        "step13b_cookies": step13b.COOKIES_ALLOWED,
        "step13b_background_daemon": step13b.BACKGROUND_DAEMON_ALLOWED,
        "step13b_background_thread": step13b.BACKGROUND_THREAD_ALLOWED,
    }
    parent_drift = [name for name, value in parent_false.items() if value is not False]
    if parent_drift:
        raise WNBAStep13ReliabilityIntegrityError(
            "Step 13C detected Step-13B safety drift: " + ", ".join(parent_drift)
        )
    if step13b.FOREGROUND_RUNTIME_SUPERVISOR_ALLOWED is not True:
        raise WNBAStep13ReliabilityIntegrityError("Step 13C Step-13B foreground permission drift.")
    own_false = {
        "step13c_default": DEFAULT_ENABLED,
        "step13c_production": PRODUCTION_ACTIVATION_ALLOWED,
        "step13c_persistence": PERSISTENCE_ALLOWED,
        "step13c_supabase": SUPABASE_WRITE_ALLOWED,
        "step13c_public_api": PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step13c_wagering": WAGERING_ALLOWED,
        "step13c_auth": AUTHENTICATION_ALLOWED,
        "step13c_cookies": COOKIES_ALLOWED,
        "step13c_background_daemon": BACKGROUND_DAEMON_ALLOWED,
        "step13c_background_thread": BACKGROUND_THREAD_ALLOWED,
        "step13c_durable_distributed_lease": DURABLE_DISTRIBUTED_LEASE_ALLOWED,
    }
    own_drift = [name for name, value in own_false.items() if value is not False]
    if own_drift:
        raise WNBAStep13ReliabilityIntegrityError(
            "Step 13C safety constant drift: " + ", ".join(own_drift)
        )
    if FOREGROUND_RELIABILITY_MANAGER_ALLOWED is not True:
        raise WNBAStep13ReliabilityIntegrityError("Step 13C foreground permission drift.")
    if PROCESS_LOCAL_ACTIVE_RUN_LEASE_ALLOWED is not True:
        raise WNBAStep13ReliabilityIntegrityError("Step 13C process-local lease permission drift.")


def _acquire_run_identity(identity: str, registry: MutableSet[str]) -> None:
    with _ACTIVE_RUN_IDENTITIES_LOCK:
        if identity in registry:
            raise WNBAStep13DuplicateRunError(
                "Step 13C refuses a duplicate active run with the same frozen request identity."
            )
        registry.add(identity)


def _release_run_identity(identity: str, registry: MutableSet[str]) -> None:
    with _ACTIVE_RUN_IDENTITIES_LOCK:
        registry.discard(identity)


def _verify_step13b_result(result: Mapping[str, Any]) -> str:
    if not isinstance(result, Mapping):
        raise WNBAStep13ReliabilityIntegrityError("Step 13C parent result must be an object.")
    if result.get("data_type") != "wnba_step13b_runtime_supervisor_response":
        raise WNBAStep13ReliabilityIntegrityError("Step 13C received wrong Step-13B data type.")
    if result.get("schema_version") != step13b.SCHEMA_VERSION:
        raise WNBAStep13ReliabilityIntegrityError("Step 13C received wrong Step-13B schema.")
    observed = str(result.get("supervisor_content_sha256") or "").strip().lower()
    surface = {
        key: deepcopy(value)
        for key, value in result.items()
        if key not in {"generated_at_utc", "supervisor_content_sha256"}
    }
    expected = _canonical_hash(surface)
    if not _valid_sha256(observed) or observed != expected:
        raise WNBAStep13ReliabilityIntegrityError(
            "Step 13C detected Step-13B supervisor content-hash mismatch."
        )
    lineage = result.get("lineage")
    if not isinstance(lineage, Mapping):
        raise WNBAStep13ReliabilityIntegrityError("Step 13C Step-13B lineage is missing.")
    if lineage.get("step13a_frozen_sha") != STEP13A_FROZEN_SHA:
        raise WNBAStep13ReliabilityIntegrityError("Step 13C Step-13A frozen lineage drift.")
    if lineage.get("step12d_frozen_sha") != STEP12D_FROZEN_SHA:
        raise WNBAStep13ReliabilityIntegrityError("Step 13C Step-12D frozen lineage drift.")
    guards = result.get("guardrails")
    if not isinstance(guards, Mapping):
        raise WNBAStep13ReliabilityIntegrityError("Step 13C Step-13B guardrails are missing.")
    if guards.get("foreground_runtime_supervisor_started") is not True:
        raise WNBAStep13ReliabilityIntegrityError("Step 13C Step-13B foreground guard drift.")
    for key in (
        "background_daemon_started",
        "background_thread_spawned",
        "cross_slate_controller_state_reuse",
        "state_persisted",
        "process_restart_state_recovery_available",
        "supabase_mutated",
        "public_fastapi_route_added",
        "production_runtime_enabled",
        "production_activation_allowed",
        "wager_action_performed",
        "authentication_used",
        "cookies_used",
        "paid_odds_vendor_used",
        "basketball_projection_changed",
        "step8_distribution_changed",
        "step9_ranking_changed",
        "step9_qualification_changed",
        "step12_presentation_changed",
    ):
        if guards.get(key) is not False:
            raise WNBAStep13ReliabilityIntegrityError(
                f"Step 13C parent Step-13B safety guard drift: {key}."
            )
    state = result.get("final_controller_state_for_restart_handoff")
    if state is not None and not isinstance(state, Mapping):
        raise WNBAStep13ReliabilityIntegrityError("Step 13C Step-13B restart handoff is invalid.")
    return observed


def _attempt_record(
    *,
    attempt: int,
    started_at: datetime,
    ended_at: datetime,
    outcome: str,
    error_type: str | None = None,
    parent_hash: str | None = None,
) -> dict[str, Any]:
    return {
        "attempt": attempt,
        "started_at_utc": started_at.isoformat(),
        "ended_at_utc": ended_at.isoformat(),
        "outcome": outcome,
        "error_type": error_type,
        "step13b_supervisor_content_sha256": parent_hash,
    }


def _build_response(
    *,
    normalized: Mapping[str, Any],
    parent_result: Mapping[str, Any] | None,
    parent_hash: str | None,
    attempts: list[dict[str, Any]],
    recovery_sleep_calls: int,
    total_recovery_sleep: float,
    outcome: str,
    stop_reason: str,
    started_at: datetime,
    ended_at: datetime,
) -> dict[str, Any]:
    initial_state = normalized["supervisor_request"].get("initial_previous_state")
    final_state = (
        deepcopy(parent_result.get("final_controller_state_for_restart_handoff"))
        if parent_result is not None
        else deepcopy(initial_state)
    )
    response = {
        "data_type": "wnba_step13c_reliability_recovery_response",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "request_content_sha256": normalized["request_content_sha256"],
        "run_identity_sha256": normalized["run_identity_sha256"],
        "status": "completed" if outcome == "success" else "recovery_exhausted",
        "health": parent_result.get("health") if parent_result is not None else "failed",
        "recovery_summary": {
            "outcome": outcome,
            "stop_reason": stop_reason,
            "max_recovery_attempts": normalized["max_recovery_attempts"],
            "attempts_executed": len(attempts),
            "successful_attempt": next(
                (item["attempt"] for item in attempts if item["outcome"] == "success"),
                None,
            ),
            "recoverable_failures": sum(
                1 for item in attempts if item["outcome"] == "recoverable_transport_failure"
            ),
            "recovery_sleep_calls": recovery_sleep_calls,
            "total_recovery_sleep_seconds": round(total_recovery_sleep, 6),
            "recovery_sleep_budget_seconds": normalized["max_total_recovery_sleep_seconds"],
            "started_at_utc": started_at.isoformat(),
            "ended_at_utc": ended_at.isoformat(),
            "elapsed_seconds": round(max(0.0, (ended_at - started_at).total_seconds()), 6),
        },
        "attempt_history": attempts,
        "latest_supervisor": deepcopy(parent_result) if parent_result is not None else None,
        "final_controller_state_for_restart_handoff": final_state,
        "lineage": {
            "step13b_frozen_sha": STEP13B_FROZEN_SHA,
            "latest_step13b_supervisor_content_sha256": parent_hash,
            "step13a_frozen_sha": STEP13A_FROZEN_SHA,
            "step12d_frozen_sha": STEP12D_FROZEN_SHA,
        },
        "guardrails": {
            "shadow_only": True,
            "foreground_reliability_manager_started": True,
            "background_daemon_started": False,
            "background_thread_spawned": False,
            "process_local_duplicate_run_guard": True,
            "cross_process_duplicate_run_guard": False,
            "durable_distributed_lease_used": False,
            "bounded_recovery_attempts": True,
            "recovery_only_for_timeout_or_connection_error": True,
            "integrity_input_disabled_errors_never_retried": True,
            "unknown_exceptions_fail_closed": True,
            "recovery_backoff_only_after_transport_failure": True,
            "frozen_refresh_cadence_unchanged": True,
            "frozen_step13b_reused_without_modification": True,
            "recovery_replay_is_read_only": True,
            "state_carried_only_from_validated_or_caller_supplied_checkpoint": True,
            "state_persisted": False,
            "durable_restart_recovery_available": False,
            "persistence_deferred_to_step14": True,
            "supabase_mutated": False,
            "public_fastapi_route_added": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
            "wager_action_performed": False,
            "authentication_used": False,
            "cookies_used": False,
            "paid_odds_vendor_used": False,
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "step9_ranking_changed": False,
            "step9_qualification_changed": False,
            "step12_presentation_changed": False,
        },
    }
    surface = {
        key: deepcopy(value)
        for key, value in response.items()
        if key not in {"generated_at_utc", "reliability_content_sha256"}
    }
    response["reliability_content_sha256"] = _canonical_hash(surface)
    return response


def run_step13c_reliability_recovery(
    request: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] | None = None,
    step13b_runner: Callable[..., Mapping[str, Any]] | None = None,
    active_run_registry: MutableSet[str] | None = None,
    stop_requested: Callable[[], bool] | None = None,
    step13a_runner: Callable[..., Mapping[str, Any]] | None = None,
    step12c_runner: Callable[..., Mapping[str, Any]] | None = None,
    draftkings_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    fanduel_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    draftkings_requester: Callable[..., Any] | None = None,
    fanduel_requester: Callable[..., Any] | None = None,
    roster_loader: Callable[[int], Mapping[str, Any]] | None = None,
    projection_loader: Callable[..., Mapping[str, Any]] | None = None,
    step12a_runner: Callable[..., Mapping[str, Any]] | None = None,
    step12b_runner: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run frozen Step 13B with process-local duplicate protection and bounded recovery."""
    _assert_safe_environment(env)
    normalized = _validate_request(request)
    now_fn = clock or (lambda: datetime.now(timezone.utc))
    sleep_fn = sleeper or time.sleep
    runner = step13b_runner or step13b.run_step13b_runtime_supervisor
    registry = _ACTIVE_RUN_IDENTITIES if active_run_registry is None else active_run_registry
    identity = normalized["run_identity_sha256"]
    _acquire_run_identity(identity, registry)
    started_at = _clock_now(now_fn)
    attempts: list[dict[str, Any]] = []
    recovery_sleep_calls = 0
    total_recovery_sleep = 0.0
    parent_result: Mapping[str, Any] | None = None
    parent_hash: str | None = None
    outcome = "recovery_exhausted"
    stop_reason = "max_recovery_attempts_reached"

    try:
        for attempt in range(1, normalized["max_recovery_attempts"] + 1):
            attempt_started = _clock_now(now_fn)
            if (attempt_started - started_at).total_seconds() < -_TIME_TOLERANCE_SECONDS:
                raise WNBAStep13ReliabilityIntegrityError("Step 13C detected clock reversal.")
            try:
                candidate = runner(
                    deepcopy(normalized["supervisor_request"]),
                    env=env,
                    clock=now_fn,
                    sleeper=sleep_fn,
                    stop_requested=stop_requested,
                    step13a_runner=step13a_runner,
                    step12c_runner=step12c_runner,
                    draftkings_fetcher=draftkings_fetcher,
                    fanduel_fetcher=fanduel_fetcher,
                    draftkings_requester=draftkings_requester,
                    fanduel_requester=fanduel_requester,
                    roster_loader=roster_loader,
                    projection_loader=projection_loader,
                    step12a_runner=step12a_runner,
                    step12b_runner=step12b_runner,
                )
                verified_hash = _verify_step13b_result(candidate)
                attempt_ended = _clock_now(now_fn)
                if (attempt_ended - attempt_started).total_seconds() < -_TIME_TOLERANCE_SECONDS:
                    raise WNBAStep13ReliabilityIntegrityError(
                        "Step 13C detected attempt clock reversal."
                    )
                parent_result = candidate
                parent_hash = verified_hash
                attempts.append(
                    _attempt_record(
                        attempt=attempt,
                        started_at=attempt_started,
                        ended_at=attempt_ended,
                        outcome="success",
                        parent_hash=verified_hash,
                    )
                )
                outcome = "success"
                stop_reason = "parent_completed"
                break
            except (
                step13b.WNBAStep13RuntimeSupervisorDisabledError,
                step13b.WNBAStep13RuntimeSupervisorInputError,
                step13b.WNBAStep13RuntimeSupervisorIntegrityError,
                WNBAStep13ReliabilityDisabledError,
                WNBAStep13ReliabilityInputError,
                WNBAStep13ReliabilityIntegrityError,
                WNBAStep13DuplicateRunError,
            ):
                raise
            except (TimeoutError, ConnectionError) as exc:
                attempt_ended = _clock_now(now_fn)
                attempts.append(
                    _attempt_record(
                        attempt=attempt,
                        started_at=attempt_started,
                        ended_at=attempt_ended,
                        outcome="recoverable_transport_failure",
                        error_type=type(exc).__name__,
                    )
                )
                if attempt >= normalized["max_recovery_attempts"]:
                    stop_reason = "max_recovery_attempts_reached"
                    break
                base = normalized["base_recovery_backoff_seconds"]
                delay = min(
                    float(base) * (2.0 ** (attempt - 1)),
                    float(MAX_SINGLE_RECOVERY_SLEEP_SECONDS),
                )
                if not math.isfinite(delay) or delay < 0.0:
                    raise WNBAStep13ReliabilityIntegrityError(
                        "Step 13C recovery backoff is invalid."
                    )
                if (
                    total_recovery_sleep + delay
                    > normalized["max_total_recovery_sleep_seconds"] + _TIME_TOLERANCE_SECONDS
                ):
                    stop_reason = "recovery_sleep_budget_reached"
                    break
                if delay > 0.0:
                    sleep_fn(delay)
                    recovery_sleep_calls += 1
                    total_recovery_sleep += delay
            except Exception as exc:
                raise WNBAStep13ReliabilityFatalError(
                    "Step 13C refuses to retry unknown runtime exception type: "
                    + type(exc).__name__
                ) from exc

        ended_at = _clock_now(now_fn)
        if (ended_at - started_at).total_seconds() < -_TIME_TOLERANCE_SECONDS:
            raise WNBAStep13ReliabilityIntegrityError("Step 13C detected terminal clock reversal.")
        response = _build_response(
            normalized=normalized,
            parent_result=parent_result,
            parent_hash=parent_hash,
            attempts=attempts,
            recovery_sleep_calls=recovery_sleep_calls,
            total_recovery_sleep=total_recovery_sleep,
            outcome=outcome,
            stop_reason=stop_reason,
            started_at=started_at,
            ended_at=ended_at,
        )
        _assert_safe_environment(env)
        return response
    finally:
        _release_run_identity(identity, registry)


__all__ = [
    "BACKGROUND_DAEMON_ALLOWED",
    "BACKGROUND_THREAD_ALLOWED",
    "DEFAULT_ENABLED",
    "DEFAULT_MAX_RECOVERY_ATTEMPTS",
    "DEFAULT_MAX_TOTAL_RECOVERY_SLEEP_SECONDS",
    "DEFAULT_RECOVERY_BACKOFF_SECONDS",
    "DURABLE_DISTRIBUTED_LEASE_ALLOWED",
    "FOREGROUND_RELIABILITY_MANAGER_ALLOWED",
    "MODEL_VERSION",
    "PROCESS_LOCAL_ACTIVE_RUN_LEASE_ALLOWED",
    "PRODUCTION_ACTIVATION_ALLOWED",
    "REQUEST_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "SOURCE",
    "STEP12D_FROZEN_SHA",
    "STEP13A_FROZEN_SHA",
    "STEP13B_FROZEN_SHA",
    "STEP13C_RELIABILITY_RECOVERY_ENABLED_ENV",
    "WNBAStep13DuplicateRunError",
    "WNBAStep13ReliabilityDisabledError",
    "WNBAStep13ReliabilityFatalError",
    "WNBAStep13ReliabilityInputError",
    "WNBAStep13ReliabilityIntegrityError",
    "build_step13c_request",
    "run_step13c_reliability_recovery",
    "step13c_reliability_recovery_enabled",
]
