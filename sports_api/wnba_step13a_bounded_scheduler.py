"""WNBA Step 13A: bounded scheduler over the frozen Step-12 live-board runtime.

Step 12 is frozen, caller-driven, and state-returning. Step 13A adds the first
scheduler layer without modifying Step 8-12. It runs a bounded foreground loop,
invokes exactly one frozen Step-12C job per scheduler tick, carries the returned
controller state in memory to the next tick, and sleeps only until the frozen
controller's next_refresh_due_at_utc.

This layer is still shadow-only and non-production. It does not start a daemon,
spawn a background worker/thread, persist state, write Supabase, expose a public
FastAPI route, authenticate to a sportsbook, use cookies, or place a wager.
Step 14 owns durable persistence; later Step-13 substeps may own deployment-host
integration after this bounded scheduler is certified.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
import time
from typing import Any

from sports_api import wnba_step12_release_freeze as step12_release
from sports_api import wnba_step12c_live_board_runtime as step12c

SOURCE = "Kyre Sports API WNBA Step 13A bounded scheduler"
SCHEMA_VERSION = "wnba_step_13a_bounded_scheduler_v1"
REQUEST_SCHEMA_VERSION = "wnba_step_13a_bounded_scheduler_request_v1"
MODEL_VERSION = "wnba_step13a_frozen_step12_foreground_scheduler_2026_regular_v1"
STEP12D_FROZEN_SHA = "48517bac86ee3f55aa4c21d6caba06c41a0a7d60"
STEP13A_BOUNDED_SCHEDULER_ENABLED_ENV = "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED"

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PERSISTENCE_ALLOWED = False
SUPABASE_WRITE_ALLOWED = False
PUBLIC_FASTAPI_ACTIVATION_ALLOWED = False
WAGERING_ALLOWED = False
AUTHENTICATION_ALLOWED = False
COOKIES_ALLOWED = False
BACKGROUND_DAEMON_ALLOWED = False
FOREGROUND_BOUNDED_SCHEDULER_ALLOWED = True

MIN_CYCLES = 1
MAX_CYCLES = 120
DEFAULT_MAX_CYCLES = 5
MIN_SLEEP_BUDGET_SECONDS = 0
MAX_SLEEP_BUDGET_SECONDS = 86_400
DEFAULT_SLEEP_BUDGET_SECONDS = 3_600
MAX_SINGLE_SLEEP_SECONDS = 3_600
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
    "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED",
    "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED",
    "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
    "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
    "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
)

_REQUEST_REQUIRED_FIELDS = {
    "data_type",
    "schema_version",
    "season",
    "slate_date",
    "max_cycles",
    "max_total_sleep_seconds",
}
_REQUEST_OPTIONAL_FIELDS = {
    "initial_previous_state",
    "controller_policy",
    "refresh_policy",
    "qualification_policy",
    "request_content_sha256",
}


class WNBAStep13BoundedSchedulerDisabledError(RuntimeError):
    """Raised when Step 13A or its frozen Step-12 parent is not safely enabled."""


class WNBAStep13BoundedSchedulerInputError(ValueError):
    """Raised when a Step-13A request is malformed."""


class WNBAStep13BoundedSchedulerIntegrityError(RuntimeError):
    """Raised when frozen parent output, lineage, state, or timing drifts."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step13a_bounded_scheduler_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP13A_BOUNDED_SCHEDULER_ENABLED_ENV))


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


def _utc(value: datetime | str, label: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        text = str(value or "").strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            result = datetime.fromisoformat(text)
        except ValueError as exc:
            raise WNBAStep13BoundedSchedulerInputError(
                f"Step 13A {label} must be timezone-aware ISO-8601."
            ) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise WNBAStep13BoundedSchedulerInputError(
            f"Step 13A {label} must include a timezone offset."
        )
    return result.astimezone(timezone.utc)


def _strict_date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise WNBAStep13BoundedSchedulerInputError(
            "Step 13A slate_date must be YYYY-MM-DD."
        ) from exc
    if parsed.isoformat() != text:
        raise WNBAStep13BoundedSchedulerInputError(
            "Step 13A slate_date must be canonical YYYY-MM-DD."
        )
    return text


def _strict_int(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise WNBAStep13BoundedSchedulerInputError(f"Step 13A {label} must be an integer.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep13BoundedSchedulerInputError(f"Step 13A {label} must be an integer.") from exc
    if isinstance(value, float) and not value.is_integer():
        raise WNBAStep13BoundedSchedulerInputError(f"Step 13A {label} must be an integer.")
    if isinstance(value, str) and str(result) != value.strip():
        raise WNBAStep13BoundedSchedulerInputError(f"Step 13A {label} must be an integer.")
    if not minimum <= result <= maximum:
        raise WNBAStep13BoundedSchedulerInputError(
            f"Step 13A {label} must be from {minimum} through {maximum}."
        )
    return result


def _strict_season(value: Any) -> int:
    season = _strict_int(value, "season", 2026, 2026)
    return season


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = os.environ if env is None else env
    if not step13a_bounded_scheduler_enabled(source):
        raise WNBAStep13BoundedSchedulerDisabledError(
            f"Step 13A requires {STEP13A_BOUNDED_SCHEDULER_ENABLED_ENV}=true."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep13BoundedSchedulerDisabledError(
            "Step 13A refuses legacy production/scheduler/persistence/write switches: "
            + ", ".join(bad)
        )
    missing = [name for name in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(name))]
    if missing:
        raise WNBAStep13BoundedSchedulerDisabledError(
            "Step 13A requires the frozen Step-12 runtime gates: " + ", ".join(missing)
        )
    if step12c.STEP12B_FROZEN_SHA != step12_release.STEP12B_FROZEN_SHA:
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A detected Step-12C parent drift.")
    if step12_release.STEP12C_FROZEN_SHA != "26902667212e670903b19002f7166ea435b238c2":
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A frozen Step-12C SHA drift.")
    if step12_release.CERTIFIED_SIMULATIONS != 5_000_000:
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A frozen simulation count drift.")
    constants = {
        "step13a_default": DEFAULT_ENABLED,
        "step13a_production": PRODUCTION_ACTIVATION_ALLOWED,
        "step13a_persistence": PERSISTENCE_ALLOWED,
        "step13a_supabase": SUPABASE_WRITE_ALLOWED,
        "step13a_public_api": PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step13a_wagering": WAGERING_ALLOWED,
        "step13a_auth": AUTHENTICATION_ALLOWED,
        "step13a_cookies": COOKIES_ALLOWED,
        "step13a_background_daemon": BACKGROUND_DAEMON_ALLOWED,
    }
    drift = [name for name, value in constants.items() if value is not False]
    if drift:
        raise WNBAStep13BoundedSchedulerIntegrityError(
            "Step 13A safety constant drift: " + ", ".join(drift)
        )
    if FOREGROUND_BOUNDED_SCHEDULER_ALLOWED is not True:
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A bounded scheduler permission drift.")
    try:
        manifest = step12_release.build_step12d_release_manifest(
            env=source,
            generated_at_utc="2026-08-28T00:00:00+00:00",
        )
    except Exception as exc:
        raise WNBAStep13BoundedSchedulerIntegrityError(
            "Step 13A could not verify the frozen Step-12D release."
        ) from exc
    if manifest.get("release_id") != step12_release.RELEASE_ID:
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A Step-12 release identity drift.")
    if (manifest.get("lineage") or {}).get("step12c_frozen_sha") != step12_release.STEP12C_FROZEN_SHA:
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A Step-12 manifest lineage drift.")
    return manifest


def _request_surface(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in request.items()
        if key != "request_content_sha256"
    }


def build_step13a_request(
    *,
    season: int,
    slate_date: str,
    max_cycles: int = DEFAULT_MAX_CYCLES,
    max_total_sleep_seconds: int = DEFAULT_SLEEP_BUDGET_SECONDS,
    initial_previous_state: Mapping[str, Any] | None = None,
    controller_policy: Mapping[str, Any] | None = None,
    refresh_policy: Mapping[str, Any] | None = None,
    qualification_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    request = {
        "data_type": "wnba_step13a_bounded_scheduler_request",
        "schema_version": REQUEST_SCHEMA_VERSION,
        "season": _strict_season(season),
        "slate_date": _strict_date(slate_date),
        "max_cycles": _strict_int(max_cycles, "max_cycles", MIN_CYCLES, MAX_CYCLES),
        "max_total_sleep_seconds": _strict_int(
            max_total_sleep_seconds,
            "max_total_sleep_seconds",
            MIN_SLEEP_BUDGET_SECONDS,
            MAX_SLEEP_BUDGET_SECONDS,
        ),
        "initial_previous_state": (
            None if initial_previous_state is None else deepcopy(dict(initial_previous_state))
        ),
        "controller_policy": dict(controller_policy or {}),
        "refresh_policy": dict(refresh_policy or {}),
        "qualification_policy": dict(qualification_policy or {}),
    }
    request["request_content_sha256"] = _canonical_hash(request)
    return request


def _validate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise WNBAStep13BoundedSchedulerInputError("Step 13A request must be an object.")
    keys = set(request)
    unknown = sorted(keys - _REQUEST_REQUIRED_FIELDS - _REQUEST_OPTIONAL_FIELDS)
    missing = sorted(_REQUEST_REQUIRED_FIELDS - keys)
    if unknown:
        raise WNBAStep13BoundedSchedulerInputError(
            "Unknown Step-13A request fields: " + ", ".join(unknown)
        )
    if missing:
        raise WNBAStep13BoundedSchedulerInputError(
            "Missing Step-13A request fields: " + ", ".join(missing)
        )
    if request.get("data_type") != "wnba_step13a_bounded_scheduler_request":
        raise WNBAStep13BoundedSchedulerInputError("Step 13A request data_type drift.")
    if request.get("schema_version") != REQUEST_SCHEMA_VERSION:
        raise WNBAStep13BoundedSchedulerInputError("Step 13A request schema_version drift.")
    for label in ("controller_policy", "refresh_policy", "qualification_policy"):
        if not isinstance(request.get(label) or {}, Mapping):
            raise WNBAStep13BoundedSchedulerInputError(f"Step 13A {label} must be an object.")
    previous = request.get("initial_previous_state")
    if previous is not None and not isinstance(previous, Mapping):
        raise WNBAStep13BoundedSchedulerInputError(
            "Step 13A initial_previous_state must be an object or null."
        )
    observed = str(request.get("request_content_sha256") or "").strip().lower()
    expected = _canonical_hash(_request_surface(request))
    if not _valid_sha256(observed) or observed != expected:
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A request content hash mismatch.")
    return {
        "season": _strict_season(request.get("season")),
        "slate_date": _strict_date(request.get("slate_date")),
        "max_cycles": _strict_int(request.get("max_cycles"), "max_cycles", MIN_CYCLES, MAX_CYCLES),
        "max_total_sleep_seconds": _strict_int(
            request.get("max_total_sleep_seconds"),
            "max_total_sleep_seconds",
            MIN_SLEEP_BUDGET_SECONDS,
            MAX_SLEEP_BUDGET_SECONDS,
        ),
        "initial_previous_state": None if previous is None else deepcopy(dict(previous)),
        "controller_policy": dict(request.get("controller_policy") or {}),
        "refresh_policy": dict(request.get("refresh_policy") or {}),
        "qualification_policy": dict(request.get("qualification_policy") or {}),
        "request_content_sha256": observed,
    }


def _verify_step12c_result(result: Mapping[str, Any], *, slate_date: str) -> str:
    if not isinstance(result, Mapping):
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A parent result must be an object.")
    if result.get("data_type") != "wnba_step12c_live_board_runtime_response":
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A received wrong Step-12C data type.")
    if result.get("schema_version") != step12c.SCHEMA_VERSION:
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A received wrong Step-12C schema.")
    if result.get("slate_date") != slate_date:
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A Step-12C slate identity mismatch.")
    observed = str(result.get("board_content_sha256") or "").strip().lower()
    surface = {
        key: deepcopy(value)
        for key, value in result.items()
        if key not in {"generated_at_utc", "board_content_sha256"}
    }
    expected = _canonical_hash(surface)
    if not _valid_sha256(observed) or observed != expected:
        raise WNBAStep13BoundedSchedulerIntegrityError(
            "Step 13A detected Step-12C board content-hash mismatch."
        )
    lineage = result.get("lineage")
    if not isinstance(lineage, Mapping):
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A Step-12C lineage is missing.")
    if lineage.get("step12b_frozen_sha") != step12_release.STEP12B_FROZEN_SHA:
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A Step-12B frozen lineage drift.")
    state = result.get("controller_state_for_next_caller_tick")
    if not isinstance(state, Mapping):
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A Step-12C controller state is missing.")
    runtime = result.get("runtime")
    if not isinstance(runtime, Mapping):
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A Step-12C runtime surface is missing.")
    next_due = runtime.get("next_refresh_due_at_utc")
    if next_due is None:
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A requires next_refresh_due_at_utc.")
    _utc(next_due, "next_refresh_due_at_utc")
    return observed


def _clock_now(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if not isinstance(value, datetime):
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A clock must return datetime.")
    try:
        return _utc(value, "clock")
    except WNBAStep13BoundedSchedulerInputError as exc:
        raise WNBAStep13BoundedSchedulerIntegrityError(str(exc)) from exc


def _tick_summary(index: int, evaluated_at: datetime, result: Mapping[str, Any], digest: str) -> dict[str, Any]:
    board = result.get("board") or {}
    runtime = result.get("runtime") or {}
    state = result.get("controller_state_for_next_caller_tick") or {}
    return {
        "tick_index": index,
        "evaluated_at_utc": evaluated_at.isoformat(),
        "status": result.get("status"),
        "health": result.get("health"),
        "board_available": board.get("available") is True,
        "top_card_count": int(board.get("top_card_count") or 0),
        "cycle_due": runtime.get("cycle_due"),
        "cycle_executed": runtime.get("cycle_executed"),
        "cycle_outcome": runtime.get("cycle_outcome"),
        "circuit_state": runtime.get("circuit_state"),
        "next_refresh_due_at_utc": runtime.get("next_refresh_due_at_utc"),
        "controller_state_content_sha256": state.get("state_content_sha256"),
        "step12c_board_content_sha256": digest,
    }


def run_step13a_bounded_scheduler(
    request: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] | None = None,
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
    """Run a bounded foreground scheduler over the frozen Step-12C runtime."""
    manifest = _assert_safe_environment(env)
    normalized = _validate_request(request)
    now_fn = clock or (lambda: datetime.now(timezone.utc))
    sleep_fn = sleeper or time.sleep
    runner = step12c_runner or step12c.run_step12c_live_board_job

    previous_state = normalized["initial_previous_state"]
    tick_history: list[dict[str, Any]] = []
    latest_result: Mapping[str, Any] | None = None
    total_sleep = 0.0
    sleep_calls = 0
    stop_reason = "max_cycles_reached"
    started_at = _clock_now(now_fn)
    prior_evaluated_at: datetime | None = None

    for index in range(1, normalized["max_cycles"] + 1):
        evaluated_at = _clock_now(now_fn)
        if prior_evaluated_at is not None and (
            evaluated_at - prior_evaluated_at
        ).total_seconds() < -_TIME_TOLERANCE_SECONDS:
            raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A detected clock reversal.")
        parent_request = step12c.build_step12c_request(
            season=normalized["season"],
            slate_date=normalized["slate_date"],
            evaluated_at=evaluated_at,
            previous_state=previous_state,
            controller_policy=normalized["controller_policy"],
            refresh_policy=normalized["refresh_policy"],
            qualification_policy=normalized["qualification_policy"],
        )
        parent_result = runner(
            parent_request,
            env=env,
            draftkings_fetcher=draftkings_fetcher,
            fanduel_fetcher=fanduel_fetcher,
            draftkings_requester=draftkings_requester,
            fanduel_requester=fanduel_requester,
            roster_loader=roster_loader,
            projection_loader=projection_loader,
            step12a_runner=step12a_runner,
            step12b_runner=step12b_runner,
        )
        parent_hash = _verify_step12c_result(parent_result, slate_date=normalized["slate_date"])
        latest_result = parent_result
        tick_history.append(_tick_summary(index, evaluated_at, parent_result, parent_hash))
        previous_state = deepcopy(dict(parent_result["controller_state_for_next_caller_tick"]))
        prior_evaluated_at = evaluated_at

        if index >= normalized["max_cycles"]:
            break

        runtime = parent_result["runtime"]
        next_due = _utc(runtime["next_refresh_due_at_utc"], "next_refresh_due_at_utc")
        if (next_due - evaluated_at).total_seconds() < -_TIME_TOLERANCE_SECONDS:
            raise WNBAStep13BoundedSchedulerIntegrityError(
                "Step 13A frozen controller returned next refresh before current evaluation time."
            )
        wall_now = _clock_now(now_fn)
        if (wall_now - evaluated_at).total_seconds() < -_TIME_TOLERANCE_SECONDS:
            raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A detected clock reversal before sleep.")
        delay = max(0.0, (next_due - wall_now).total_seconds())
        if not math.isfinite(delay) or delay > MAX_SINGLE_SLEEP_SECONDS + _TIME_TOLERANCE_SECONDS:
            raise WNBAStep13BoundedSchedulerIntegrityError(
                "Step 13A frozen controller requested an out-of-bounds sleep interval."
            )
        if total_sleep + delay > normalized["max_total_sleep_seconds"] + _TIME_TOLERANCE_SECONDS:
            stop_reason = "sleep_budget_reached"
            break
        if delay > 0.0:
            sleep_fn(delay)
            total_sleep += delay
            sleep_calls += 1

    ended_at = _clock_now(now_fn)
    if (ended_at - started_at).total_seconds() < -_TIME_TOLERANCE_SECONDS:
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A detected terminal clock reversal.")
    if latest_result is None:
        raise WNBAStep13BoundedSchedulerIntegrityError("Step 13A executed no scheduler ticks.")

    response = {
        "data_type": "wnba_step13a_bounded_scheduler_response",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "request_content_sha256": normalized["request_content_sha256"],
        "status": "completed" if stop_reason == "max_cycles_reached" else "bounded_stop",
        "health": latest_result.get("health"),
        "slate_date": normalized["slate_date"],
        "scheduler_summary": {
            "requested_cycles": normalized["max_cycles"],
            "executed_ticks": len(tick_history),
            "sleep_calls": sleep_calls,
            "total_sleep_seconds": round(total_sleep, 6),
            "sleep_budget_seconds": normalized["max_total_sleep_seconds"],
            "stop_reason": stop_reason,
            "started_at_utc": started_at.isoformat(),
            "ended_at_utc": ended_at.isoformat(),
        },
        "tick_history": tick_history,
        "latest_board": deepcopy(latest_result.get("board") or {}),
        "latest_runtime": deepcopy(latest_result.get("runtime") or {}),
        "final_controller_state_for_next_process": deepcopy(previous_state),
        "lineage": {
            "step12d_frozen_sha": STEP12D_FROZEN_SHA,
            "step12_release_id": manifest.get("release_id"),
            "step12_release_content_sha256": manifest.get("release_content_sha256"),
            "step12c_frozen_sha": step12_release.STEP12C_FROZEN_SHA,
            "step12b_frozen_sha": step12_release.STEP12B_FROZEN_SHA,
            "step12a_frozen_sha": step12_release.STEP12A_FROZEN_SHA,
            "step11e_frozen_sha": step12_release.STEP11E_FROZEN_SHA,
            "step8_frozen_sha": step12_release.STEP8_FROZEN_SHA,
        },
        "guardrails": {
            "shadow_only": True,
            "bounded_foreground_scheduler_started": True,
            "background_daemon_started": False,
            "background_thread_spawned": False,
            "one_step12c_call_per_scheduler_tick": True,
            "frozen_controller_owns_refresh_cadence": True,
            "sleep_until_frozen_next_refresh_due": True,
            "controller_state_carried_forward_in_memory": True,
            "state_persisted": False,
            "process_restart_state_recovery_available": False,
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
    hash_surface = {
        key: deepcopy(value)
        for key, value in response.items()
        if key not in {"generated_at_utc", "scheduler_content_sha256"}
    }
    response["scheduler_content_sha256"] = _canonical_hash(hash_surface)
    _assert_safe_environment(env)
    return response


__all__ = [
    "BACKGROUND_DAEMON_ALLOWED",
    "DEFAULT_ENABLED",
    "DEFAULT_MAX_CYCLES",
    "DEFAULT_SLEEP_BUDGET_SECONDS",
    "FOREGROUND_BOUNDED_SCHEDULER_ALLOWED",
    "MODEL_VERSION",
    "PRODUCTION_ACTIVATION_ALLOWED",
    "REQUEST_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "SOURCE",
    "STEP12D_FROZEN_SHA",
    "STEP13A_BOUNDED_SCHEDULER_ENABLED_ENV",
    "WNBAStep13BoundedSchedulerDisabledError",
    "WNBAStep13BoundedSchedulerInputError",
    "WNBAStep13BoundedSchedulerIntegrityError",
    "build_step13a_request",
    "run_step13a_bounded_scheduler",
    "step13a_bounded_scheduler_enabled",
]
