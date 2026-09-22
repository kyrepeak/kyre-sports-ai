"""WNBA Step 13B: controlled runtime supervisor over frozen Step 13A.

Step 13A owns bounded scheduler execution and the frozen Step-11E controller owns
refresh cadence/circuit timing. Step 13B adds a foreground lifecycle supervisor
that can chain multiple bounded Step-13A sessions, observe graceful shutdown,
wait only until the frozen controller's returned next-refresh time between
sessions, and protect slate-date rollover.

The supervisor is still shadow-only and non-production. It does not daemonize,
spawn background threads/workers, persist controller state, write Supabase,
expose a public FastAPI route, authenticate to sportsbooks, use cookies, or
place wagers. Durable restart recovery remains Step 14 work.
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
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sports_api import wnba_step12_release_freeze as step12_release
from sports_api import wnba_step13a_bounded_scheduler as step13a

SOURCE = "Kyre Sports API WNBA Step 13B controlled runtime supervisor"
SCHEMA_VERSION = "wnba_step_13b_runtime_supervisor_v1"
REQUEST_SCHEMA_VERSION = "wnba_step_13b_runtime_supervisor_request_v1"
MODEL_VERSION = "wnba_step13b_foreground_lifecycle_supervisor_2026_regular_v1"
STEP13A_FROZEN_SHA = "eaa744ae097a94d5f54c490ab13ca7d66bb725c2"
STEP12D_FROZEN_SHA = step13a.STEP12D_FROZEN_SHA
STEP13B_RUNTIME_SUPERVISOR_ENABLED_ENV = "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED"

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
FOREGROUND_RUNTIME_SUPERVISOR_ALLOWED = True

MIN_SESSIONS = 1
MAX_SESSIONS = 48
DEFAULT_MAX_SESSIONS = 4
MIN_RUNTIME_SECONDS = 1
MAX_RUNTIME_SECONDS = 86_400
DEFAULT_MAX_RUNTIME_SECONDS = 21_600
MIN_INTERSESSION_SLEEP_BUDGET_SECONDS = 0
MAX_INTERSESSION_SLEEP_BUDGET_SECONDS = 86_400
DEFAULT_INTERSESSION_SLEEP_BUDGET_SECONDS = 3_600
MAX_SINGLE_INTERSESSION_SLEEP_SECONDS = 3_600
DEFAULT_SLATE_TIMEZONE = "America/New_York"
ROLLOVER_POLICIES = ("stop", "advance_reset")
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
    "season",
    "initial_slate_date",
    "slate_timezone",
    "rollover_policy",
    "max_supervisor_sessions",
    "max_supervisor_runtime_seconds",
    "max_total_intersession_sleep_seconds",
    "scheduler_cycles_per_session",
    "scheduler_sleep_budget_seconds_per_session",
}
_REQUEST_OPTIONAL_FIELDS = {
    "initial_previous_state",
    "controller_policy",
    "refresh_policy",
    "qualification_policy",
    "request_content_sha256",
}


class WNBAStep13RuntimeSupervisorDisabledError(RuntimeError):
    """Raised when Step 13B or its frozen parents are not safely enabled."""


class WNBAStep13RuntimeSupervisorInputError(ValueError):
    """Raised when a Step-13B request is malformed."""


class WNBAStep13RuntimeSupervisorIntegrityError(RuntimeError):
    """Raised when frozen scheduler output, lineage, timing, or lifecycle drifts."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step13b_runtime_supervisor_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP13B_RUNTIME_SUPERVISOR_ENABLED_ENV))


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
            raise WNBAStep13RuntimeSupervisorInputError(
                f"Step 13B {label} must be timezone-aware ISO-8601."
            ) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise WNBAStep13RuntimeSupervisorInputError(
            f"Step 13B {label} must include a timezone offset."
        )
    return result.astimezone(timezone.utc)


def _strict_date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise WNBAStep13RuntimeSupervisorInputError(
            "Step 13B initial_slate_date must be YYYY-MM-DD."
        ) from exc
    if parsed.isoformat() != text:
        raise WNBAStep13RuntimeSupervisorInputError(
            "Step 13B initial_slate_date must be canonical YYYY-MM-DD."
        )
    if parsed.year != 2026:
        raise WNBAStep13RuntimeSupervisorInputError(
            "Step 13B is certified only for the 2026 WNBA Regular Season."
        )
    return text


def _strict_int(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise WNBAStep13RuntimeSupervisorInputError(f"Step 13B {label} must be an integer.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep13RuntimeSupervisorInputError(f"Step 13B {label} must be an integer.") from exc
    if isinstance(value, float) and not value.is_integer():
        raise WNBAStep13RuntimeSupervisorInputError(f"Step 13B {label} must be an integer.")
    if isinstance(value, str) and str(result) != value.strip():
        raise WNBAStep13RuntimeSupervisorInputError(f"Step 13B {label} must be an integer.")
    if not minimum <= result <= maximum:
        raise WNBAStep13RuntimeSupervisorInputError(
            f"Step 13B {label} must be from {minimum} through {maximum}."
        )
    return result


def _strict_season(value: Any) -> int:
    return _strict_int(value, "season", 2026, 2026)


def _timezone(value: Any) -> ZoneInfo:
    name = str(value or "").strip()
    if not name:
        raise WNBAStep13RuntimeSupervisorInputError("Step 13B slate_timezone is required.")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise WNBAStep13RuntimeSupervisorInputError(
            f"Step 13B slate_timezone is unknown: {name}."
        ) from exc


def _rollover_policy(value: Any) -> str:
    policy = str(value or "").strip().casefold()
    if policy not in ROLLOVER_POLICIES:
        raise WNBAStep13RuntimeSupervisorInputError(
            "Step 13B rollover_policy must be stop or advance_reset."
        )
    return policy


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    if not step13b_runtime_supervisor_enabled(source):
        raise WNBAStep13RuntimeSupervisorDisabledError(
            f"Step 13B requires {STEP13B_RUNTIME_SUPERVISOR_ENABLED_ENV}=true."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep13RuntimeSupervisorDisabledError(
            "Step 13B refuses legacy production/scheduler/persistence/write switches: "
            + ", ".join(bad)
        )
    missing = [name for name in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(name))]
    if missing:
        raise WNBAStep13RuntimeSupervisorDisabledError(
            "Step 13B requires frozen Step-13A/Step-12 gates: " + ", ".join(missing)
        )
    if step13a.STEP12D_FROZEN_SHA != step12_release.BRANCH and False:
        # Deliberately unreachable; the exact SHA assertion below is the contract.
        raise WNBAStep13RuntimeSupervisorIntegrityError("unreachable")
    if step13a.STEP12D_FROZEN_SHA != "48517bac86ee3f55aa4c21d6caba06c41a0a7d60":
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B frozen Step-12D lineage drift.")
    if step13a.DEFAULT_ENABLED is not False:
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13A must remain default-OFF.")
    if step13a.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13A production activation drift.")
    if step13a.PERSISTENCE_ALLOWED is not False or step13a.SUPABASE_WRITE_ALLOWED is not False:
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13A persistence safety drift.")
    if step13a.BACKGROUND_DAEMON_ALLOWED is not False:
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13A background-daemon safety drift.")
    if step13a.FOREGROUND_BOUNDED_SCHEDULER_ALLOWED is not True:
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13A bounded scheduler permission drift.")
    constants = {
        "step13b_default": DEFAULT_ENABLED,
        "step13b_production": PRODUCTION_ACTIVATION_ALLOWED,
        "step13b_persistence": PERSISTENCE_ALLOWED,
        "step13b_supabase": SUPABASE_WRITE_ALLOWED,
        "step13b_public_api": PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step13b_wagering": WAGERING_ALLOWED,
        "step13b_auth": AUTHENTICATION_ALLOWED,
        "step13b_cookies": COOKIES_ALLOWED,
        "step13b_background_daemon": BACKGROUND_DAEMON_ALLOWED,
        "step13b_background_thread": BACKGROUND_THREAD_ALLOWED,
    }
    drift = [name for name, value in constants.items() if value is not False]
    if drift:
        raise WNBAStep13RuntimeSupervisorIntegrityError(
            "Step 13B safety constant drift: " + ", ".join(drift)
        )
    if FOREGROUND_RUNTIME_SUPERVISOR_ALLOWED is not True:
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B foreground supervisor permission drift.")


def _request_surface(request: Mapping[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in request.items() if key != "request_content_sha256"}


def build_step13b_request(
    *,
    season: int,
    initial_slate_date: str,
    slate_timezone: str = DEFAULT_SLATE_TIMEZONE,
    rollover_policy: str = "stop",
    max_supervisor_sessions: int = DEFAULT_MAX_SESSIONS,
    max_supervisor_runtime_seconds: int = DEFAULT_MAX_RUNTIME_SECONDS,
    max_total_intersession_sleep_seconds: int = DEFAULT_INTERSESSION_SLEEP_BUDGET_SECONDS,
    scheduler_cycles_per_session: int = step13a.DEFAULT_MAX_CYCLES,
    scheduler_sleep_budget_seconds_per_session: int = step13a.DEFAULT_SLEEP_BUDGET_SECONDS,
    initial_previous_state: Mapping[str, Any] | None = None,
    controller_policy: Mapping[str, Any] | None = None,
    refresh_policy: Mapping[str, Any] | None = None,
    qualification_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    tz = _timezone(slate_timezone)
    request = {
        "data_type": "wnba_step13b_runtime_supervisor_request",
        "schema_version": REQUEST_SCHEMA_VERSION,
        "season": _strict_season(season),
        "initial_slate_date": _strict_date(initial_slate_date),
        "slate_timezone": tz.key,
        "rollover_policy": _rollover_policy(rollover_policy),
        "max_supervisor_sessions": _strict_int(
            max_supervisor_sessions, "max_supervisor_sessions", MIN_SESSIONS, MAX_SESSIONS
        ),
        "max_supervisor_runtime_seconds": _strict_int(
            max_supervisor_runtime_seconds,
            "max_supervisor_runtime_seconds",
            MIN_RUNTIME_SECONDS,
            MAX_RUNTIME_SECONDS,
        ),
        "max_total_intersession_sleep_seconds": _strict_int(
            max_total_intersession_sleep_seconds,
            "max_total_intersession_sleep_seconds",
            MIN_INTERSESSION_SLEEP_BUDGET_SECONDS,
            MAX_INTERSESSION_SLEEP_BUDGET_SECONDS,
        ),
        "scheduler_cycles_per_session": _strict_int(
            scheduler_cycles_per_session,
            "scheduler_cycles_per_session",
            step13a.MIN_CYCLES,
            step13a.MAX_CYCLES,
        ),
        "scheduler_sleep_budget_seconds_per_session": _strict_int(
            scheduler_sleep_budget_seconds_per_session,
            "scheduler_sleep_budget_seconds_per_session",
            step13a.MIN_SLEEP_BUDGET_SECONDS,
            step13a.MAX_SLEEP_BUDGET_SECONDS,
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
        raise WNBAStep13RuntimeSupervisorInputError("Step 13B request must be an object.")
    keys = set(request)
    unknown = sorted(keys - _REQUEST_REQUIRED_FIELDS - _REQUEST_OPTIONAL_FIELDS)
    missing = sorted(_REQUEST_REQUIRED_FIELDS - keys)
    if unknown:
        raise WNBAStep13RuntimeSupervisorInputError(
            "Unknown Step-13B request fields: " + ", ".join(unknown)
        )
    if missing:
        raise WNBAStep13RuntimeSupervisorInputError(
            "Missing Step-13B request fields: " + ", ".join(missing)
        )
    if request.get("data_type") != "wnba_step13b_runtime_supervisor_request":
        raise WNBAStep13RuntimeSupervisorInputError("Step 13B request data_type drift.")
    if request.get("schema_version") != REQUEST_SCHEMA_VERSION:
        raise WNBAStep13RuntimeSupervisorInputError("Step 13B request schema_version drift.")
    previous = request.get("initial_previous_state")
    if previous is not None and not isinstance(previous, Mapping):
        raise WNBAStep13RuntimeSupervisorInputError(
            "Step 13B initial_previous_state must be an object or null."
        )
    for label in ("controller_policy", "refresh_policy", "qualification_policy"):
        if not isinstance(request.get(label) or {}, Mapping):
            raise WNBAStep13RuntimeSupervisorInputError(f"Step 13B {label} must be an object.")
    observed = str(request.get("request_content_sha256") or "").strip().lower()
    expected = _canonical_hash(_request_surface(request))
    if not _valid_sha256(observed) or observed != expected:
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B request content hash mismatch.")
    tz = _timezone(request.get("slate_timezone"))
    return {
        "season": _strict_season(request.get("season")),
        "initial_slate_date": _strict_date(request.get("initial_slate_date")),
        "slate_timezone": tz,
        "slate_timezone_name": tz.key,
        "rollover_policy": _rollover_policy(request.get("rollover_policy")),
        "max_supervisor_sessions": _strict_int(
            request.get("max_supervisor_sessions"),
            "max_supervisor_sessions",
            MIN_SESSIONS,
            MAX_SESSIONS,
        ),
        "max_supervisor_runtime_seconds": _strict_int(
            request.get("max_supervisor_runtime_seconds"),
            "max_supervisor_runtime_seconds",
            MIN_RUNTIME_SECONDS,
            MAX_RUNTIME_SECONDS,
        ),
        "max_total_intersession_sleep_seconds": _strict_int(
            request.get("max_total_intersession_sleep_seconds"),
            "max_total_intersession_sleep_seconds",
            MIN_INTERSESSION_SLEEP_BUDGET_SECONDS,
            MAX_INTERSESSION_SLEEP_BUDGET_SECONDS,
        ),
        "scheduler_cycles_per_session": _strict_int(
            request.get("scheduler_cycles_per_session"),
            "scheduler_cycles_per_session",
            step13a.MIN_CYCLES,
            step13a.MAX_CYCLES,
        ),
        "scheduler_sleep_budget_seconds_per_session": _strict_int(
            request.get("scheduler_sleep_budget_seconds_per_session"),
            "scheduler_sleep_budget_seconds_per_session",
            step13a.MIN_SLEEP_BUDGET_SECONDS,
            step13a.MAX_SLEEP_BUDGET_SECONDS,
        ),
        "initial_previous_state": None if previous is None else deepcopy(dict(previous)),
        "controller_policy": dict(request.get("controller_policy") or {}),
        "refresh_policy": dict(request.get("refresh_policy") or {}),
        "qualification_policy": dict(request.get("qualification_policy") or {}),
        "request_content_sha256": observed,
    }


def _clock_now(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if not isinstance(value, datetime):
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B clock must return datetime.")
    try:
        return _utc(value, "clock")
    except WNBAStep13RuntimeSupervisorInputError as exc:
        raise WNBAStep13RuntimeSupervisorIntegrityError(str(exc)) from exc


def _local_slate(now_utc: datetime, tz: ZoneInfo) -> str:
    return now_utc.astimezone(tz).date().isoformat()


def _verify_step13a_result(result: Mapping[str, Any], *, slate_date: str) -> str:
    if not isinstance(result, Mapping):
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B parent result must be an object.")
    if result.get("data_type") != "wnba_step13a_bounded_scheduler_response":
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B received wrong Step-13A data type.")
    if result.get("schema_version") != step13a.SCHEMA_VERSION:
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B received wrong Step-13A schema.")
    if result.get("slate_date") != slate_date:
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B Step-13A slate identity mismatch.")
    observed = str(result.get("scheduler_content_sha256") or "").strip().lower()
    surface = {
        key: deepcopy(value)
        for key, value in result.items()
        if key not in {"generated_at_utc", "scheduler_content_sha256"}
    }
    expected = _canonical_hash(surface)
    if not _valid_sha256(observed) or observed != expected:
        raise WNBAStep13RuntimeSupervisorIntegrityError(
            "Step 13B detected Step-13A scheduler content-hash mismatch."
        )
    lineage = result.get("lineage")
    if not isinstance(lineage, Mapping) or lineage.get("step12d_frozen_sha") != STEP12D_FROZEN_SHA:
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B Step-13A frozen lineage drift.")
    state = result.get("final_controller_state_for_next_process")
    if not isinstance(state, Mapping):
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B final Step-13A controller state is missing.")
    state_hash = state.get("state_content_sha256")
    if not _valid_sha256(state_hash):
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B final controller state hash is invalid.")
    runtime = result.get("latest_runtime")
    if not isinstance(runtime, Mapping) or runtime.get("next_refresh_due_at_utc") is None:
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B Step-13A next refresh time is missing.")
    _utc(runtime.get("next_refresh_due_at_utc"), "next_refresh_due_at_utc")
    guards = result.get("guardrails")
    if not isinstance(guards, Mapping):
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B Step-13A guardrails are missing.")
    for key in (
        "background_daemon_started",
        "background_thread_spawned",
        "state_persisted",
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
            raise WNBAStep13RuntimeSupervisorIntegrityError(
                f"Step 13B parent Step-13A safety guard drift: {key}."
            )
    return observed


def _lifecycle_event(events: list[dict[str, Any]], state: str, at: datetime, **detail: Any) -> None:
    event = {"sequence": len(events) + 1, "state": state, "at_utc": at.isoformat()}
    event.update(detail)
    events.append(event)


def run_step13b_runtime_supervisor(
    request: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] | None = None,
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
    """Supervise multiple bounded Step-13A scheduler sessions in the foreground."""
    _assert_safe_environment(env)
    normalized = _validate_request(request)
    now_fn = clock or (lambda: datetime.now(timezone.utc))
    sleep_fn = sleeper or time.sleep
    stop_fn = stop_requested or (lambda: False)
    runner = step13a_runner or step13a.run_step13a_bounded_scheduler

    started_at = _clock_now(now_fn)
    active_slate = normalized["initial_slate_date"]
    previous_state = normalized["initial_previous_state"]
    lifecycle: list[dict[str, Any]] = []
    session_history: list[dict[str, Any]] = []
    rollover_history: list[dict[str, Any]] = []
    latest_result: Mapping[str, Any] | None = None
    latest_parent_hash: str | None = None
    intersession_sleep_calls = 0
    total_intersession_sleep = 0.0
    stop_reason = "max_sessions_reached"
    _lifecycle_event(lifecycle, "starting", started_at, slate_date=active_slate)
    _lifecycle_event(lifecycle, "running", started_at, slate_date=active_slate)

    for session_index in range(1, normalized["max_supervisor_sessions"] + 1):
        now = _clock_now(now_fn)
        elapsed = (now - started_at).total_seconds()
        if elapsed < -_TIME_TOLERANCE_SECONDS:
            raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B detected clock reversal.")
        if elapsed > normalized["max_supervisor_runtime_seconds"] + _TIME_TOLERANCE_SECONDS:
            stop_reason = "runtime_budget_reached"
            break
        if stop_fn():
            stop_reason = "graceful_shutdown_requested"
            break

        resolved_slate = _local_slate(now, normalized["slate_timezone"])
        if resolved_slate < active_slate:
            raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B detected local slate-date reversal.")
        if resolved_slate != active_slate:
            if not resolved_slate.startswith("2026-"):
                stop_reason = "season_boundary_reached"
                break
            if normalized["rollover_policy"] == "stop":
                stop_reason = "slate_rollover_required"
                break
            rollover = {
                "from_slate_date": active_slate,
                "to_slate_date": resolved_slate,
                "at_utc": now.isoformat(),
                "controller_state_reset": True,
            }
            rollover_history.append(rollover)
            _lifecycle_event(
                lifecycle,
                "slate_rollover",
                now,
                from_slate_date=active_slate,
                to_slate_date=resolved_slate,
                controller_state_reset=True,
            )
            active_slate = resolved_slate
            previous_state = None

        parent_request = step13a.build_step13a_request(
            season=normalized["season"],
            slate_date=active_slate,
            max_cycles=normalized["scheduler_cycles_per_session"],
            max_total_sleep_seconds=normalized["scheduler_sleep_budget_seconds_per_session"],
            initial_previous_state=previous_state,
            controller_policy=normalized["controller_policy"],
            refresh_policy=normalized["refresh_policy"],
            qualification_policy=normalized["qualification_policy"],
        )
        session_started = _clock_now(now_fn)
        _lifecycle_event(
            lifecycle,
            "scheduler_session_started",
            session_started,
            session_index=session_index,
            slate_date=active_slate,
        )
        parent_result = runner(
            parent_request,
            env=env,
            clock=now_fn,
            sleeper=sleep_fn,
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
        parent_hash = _verify_step13a_result(parent_result, slate_date=active_slate)
        latest_result = parent_result
        latest_parent_hash = parent_hash
        previous_state = deepcopy(dict(parent_result["final_controller_state_for_next_process"]))
        session_ended = _clock_now(now_fn)
        if (session_ended - session_started).total_seconds() < -_TIME_TOLERANCE_SECONDS:
            raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B detected session clock reversal.")
        session_history.append(
            {
                "session_index": session_index,
                "slate_date": active_slate,
                "started_at_utc": session_started.isoformat(),
                "ended_at_utc": session_ended.isoformat(),
                "status": parent_result.get("status"),
                "health": parent_result.get("health"),
                "scheduler_stop_reason": (parent_result.get("scheduler_summary") or {}).get("stop_reason"),
                "executed_ticks": (parent_result.get("scheduler_summary") or {}).get("executed_ticks"),
                "latest_board_available": (parent_result.get("latest_board") or {}).get("available") is True,
                "next_refresh_due_at_utc": (parent_result.get("latest_runtime") or {}).get("next_refresh_due_at_utc"),
                "final_controller_state_content_sha256": previous_state.get("state_content_sha256"),
                "step13a_scheduler_content_sha256": parent_hash,
            }
        )
        _lifecycle_event(
            lifecycle,
            "scheduler_session_completed",
            session_ended,
            session_index=session_index,
            slate_date=active_slate,
            health=parent_result.get("health"),
        )

        if session_index >= normalized["max_supervisor_sessions"]:
            break
        if stop_fn():
            stop_reason = "graceful_shutdown_requested"
            break

        next_due = _utc(
            (parent_result.get("latest_runtime") or {}).get("next_refresh_due_at_utc"),
            "next_refresh_due_at_utc",
        )
        wall_now = _clock_now(now_fn)
        if (wall_now - session_ended).total_seconds() < -_TIME_TOLERANCE_SECONDS:
            raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B detected clock reversal before wait.")
        if (next_due - session_ended).total_seconds() < -_TIME_TOLERANCE_SECONDS:
            raise WNBAStep13RuntimeSupervisorIntegrityError(
                "Step 13B frozen scheduler returned next refresh before session completion."
            )
        delay = max(0.0, (next_due - wall_now).total_seconds())
        if not math.isfinite(delay) or delay > MAX_SINGLE_INTERSESSION_SLEEP_SECONDS + _TIME_TOLERANCE_SECONDS:
            raise WNBAStep13RuntimeSupervisorIntegrityError(
                "Step 13B frozen scheduler requested an out-of-bounds intersession wait."
            )
        elapsed_with_wait = (wall_now - started_at).total_seconds() + delay
        if elapsed_with_wait > normalized["max_supervisor_runtime_seconds"] + _TIME_TOLERANCE_SECONDS:
            stop_reason = "runtime_budget_reached"
            break
        if (
            total_intersession_sleep + delay
            > normalized["max_total_intersession_sleep_seconds"] + _TIME_TOLERANCE_SECONDS
        ):
            stop_reason = "intersession_sleep_budget_reached"
            break
        due_slate = _local_slate(next_due, normalized["slate_timezone"])
        if due_slate < active_slate:
            raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B next due time reverses slate date.")
        if due_slate != active_slate and normalized["rollover_policy"] == "stop":
            stop_reason = "slate_rollover_required"
            break
        if not due_slate.startswith("2026-"):
            stop_reason = "season_boundary_reached"
            break

        if delay > 0.0:
            _lifecycle_event(
                lifecycle,
                "waiting_for_frozen_next_refresh",
                wall_now,
                delay_seconds=round(delay, 6),
                next_refresh_due_at_utc=next_due.isoformat(),
            )
            sleep_fn(delay)
            total_intersession_sleep += delay
            intersession_sleep_calls += 1

    ended_at = _clock_now(now_fn)
    if (ended_at - started_at).total_seconds() < -_TIME_TOLERANCE_SECONDS:
        raise WNBAStep13RuntimeSupervisorIntegrityError("Step 13B detected terminal clock reversal.")
    _lifecycle_event(lifecycle, "stopping", ended_at, reason=stop_reason, slate_date=active_slate)
    _lifecycle_event(lifecycle, "stopped", ended_at, reason=stop_reason, slate_date=active_slate)

    response = {
        "data_type": "wnba_step13b_runtime_supervisor_response",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "request_content_sha256": normalized["request_content_sha256"],
        "status": "stopped",
        "health": latest_result.get("health") if latest_result is not None else "not_started",
        "active_slate_date": active_slate,
        "supervisor_summary": {
            "requested_max_sessions": normalized["max_supervisor_sessions"],
            "completed_sessions": len(session_history),
            "stop_reason": stop_reason,
            "started_at_utc": started_at.isoformat(),
            "ended_at_utc": ended_at.isoformat(),
            "elapsed_seconds": round(max(0.0, (ended_at - started_at).total_seconds()), 6),
            "max_runtime_seconds": normalized["max_supervisor_runtime_seconds"],
            "intersession_sleep_calls": intersession_sleep_calls,
            "total_intersession_sleep_seconds": round(total_intersession_sleep, 6),
            "intersession_sleep_budget_seconds": normalized["max_total_intersession_sleep_seconds"],
            "rollover_count": len(rollover_history),
            "slate_timezone": normalized["slate_timezone_name"],
            "rollover_policy": normalized["rollover_policy"],
        },
        "lifecycle": lifecycle,
        "session_history": session_history,
        "rollover_history": rollover_history,
        "latest_scheduler": deepcopy(latest_result) if latest_result is not None else None,
        "final_controller_state_for_restart_handoff": deepcopy(previous_state),
        "lineage": {
            "step13a_frozen_sha": STEP13A_FROZEN_SHA,
            "latest_step13a_scheduler_content_sha256": latest_parent_hash,
            "step12d_frozen_sha": STEP12D_FROZEN_SHA,
            "step12_release_id": step12_release.RELEASE_ID,
            "step12c_frozen_sha": step12_release.STEP12C_FROZEN_SHA,
            "step12b_frozen_sha": step12_release.STEP12B_FROZEN_SHA,
            "step12a_frozen_sha": step12_release.STEP12A_FROZEN_SHA,
            "step11e_frozen_sha": step12_release.STEP11E_FROZEN_SHA,
            "step8_frozen_sha": step12_release.STEP8_FROZEN_SHA,
        },
        "guardrails": {
            "shadow_only": True,
            "foreground_runtime_supervisor_started": True,
            "background_daemon_started": False,
            "background_thread_spawned": False,
            "step13a_scheduler_reused_without_modification": True,
            "frozen_controller_owns_refresh_cadence": True,
            "intersession_wait_uses_frozen_next_refresh_due": True,
            "graceful_shutdown_hook_supported": True,
            "slate_rollover_protected": True,
            "cross_slate_controller_state_reuse": False,
            "advance_rollover_resets_controller_state": True,
            "state_carried_forward_in_memory": True,
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
        if key not in {"generated_at_utc", "supervisor_content_sha256"}
    }
    response["supervisor_content_sha256"] = _canonical_hash(hash_surface)
    _assert_safe_environment(env)
    return response


__all__ = [
    "BACKGROUND_DAEMON_ALLOWED",
    "BACKGROUND_THREAD_ALLOWED",
    "DEFAULT_ENABLED",
    "DEFAULT_MAX_RUNTIME_SECONDS",
    "DEFAULT_MAX_SESSIONS",
    "DEFAULT_SLATE_TIMEZONE",
    "FOREGROUND_RUNTIME_SUPERVISOR_ALLOWED",
    "MODEL_VERSION",
    "PRODUCTION_ACTIVATION_ALLOWED",
    "REQUEST_SCHEMA_VERSION",
    "ROLLOVER_POLICIES",
    "SCHEMA_VERSION",
    "SOURCE",
    "STEP12D_FROZEN_SHA",
    "STEP13A_FROZEN_SHA",
    "STEP13B_RUNTIME_SUPERVISOR_ENABLED_ENV",
    "WNBAStep13RuntimeSupervisorDisabledError",
    "WNBAStep13RuntimeSupervisorInputError",
    "WNBAStep13RuntimeSupervisorIntegrityError",
    "build_step13b_request",
    "run_step13b_runtime_supervisor",
    "step13b_runtime_supervisor_enabled",
]
