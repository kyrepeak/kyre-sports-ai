"""WNBA Step 17C: production reliability and monitoring.

This layer is deliberately read-only. It observes the certified Step-17B
single-leader durable runtime and classifies operational health without
starting a scheduler, opening a database connection, calling a sportsbook,
running a model, or mutating any checkpoint.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
from typing import Any, Callable, Mapping

from sports_api import wnba_step17b_always_on_runtime as step17b

SOURCE = "Kyre Sports API WNBA Step 17C production reliability monitor"
SCHEMA_VERSION = "wnba_step_17c_production_reliability_v1"
MONITOR_VERSION = "wnba_step17c_read_only_watchdog_v1"
BRANCH = "wnba-step17c-production-reliability-monitoring-20260828"
STEP17B_CERTIFIED_PARENT_SHA = "8f6ba0b3e4cd3d07466a2545a870cab7121decfe"

STEP17C_ENABLED_ENV = "WNBA_STEP17C_MONITORING_ENABLED"
DEFAULT_ENABLED = False
MIN_HEARTBEAT_STALE_SECONDS = 120
MIN_CYCLE_STALE_SECONDS = 180
MIN_STARTUP_GRACE_SECONDS = 120


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step17c_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP17C_ENABLED_ENV))


def _utc_now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _dt(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _age_seconds(now: datetime, value: object) -> float | None:
    parsed = _dt(value)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds())


def _loop_seconds(environment: Mapping[str, str]) -> int | None:
    raw = environment.get(step17b.STEP17B_LOOP_SECONDS_ENV, str(step17b.DEFAULT_LOOP_SECONDS))
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if not step17b.MIN_LOOP_SECONDS <= value <= step17b.MAX_LOOP_SECONDS:
        return None
    return value


def _sanitized_runtime_snapshot(status: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "enabled",
        "running",
        "role",
        "leadership_acquired",
        "started_at_utc",
        "heartbeat_at_utc",
        "next_cycle_due_at_utc",
        "cycle_count",
        "success_count",
        "failure_count",
        "leadership_miss_count",
        "duplicate_lease_skip_count",
        "last_cycle_started_at_utc",
        "last_cycle_finished_at_utc",
        "last_slate_date",
        "last_status",
        "last_error_class",
        "last_checkpoint_version",
        "recovered_from_checkpoint",
        "database_secret_exposed",
        "legacy_production_switches_enabled",
        "new_render_service_created",
    )
    return {key: deepcopy(status.get(key)) for key in allowed}


def build_step17c_production_reliability(
    *,
    now_utc: datetime | None = None,
    env: Mapping[str, str] | None = None,
    status_getter: Callable[[], Mapping[str, Any]] = step17b.get_step17b_status,
) -> dict[str, Any]:
    environment = dict(os.environ if env is None else env)
    now = _utc_now(now_utc)
    monitor_enabled = step17c_enabled(environment)
    status = dict(status_getter() or {})
    snapshot = _sanitized_runtime_snapshot(status)
    incidents: list[dict[str, str]] = []

    def incident(code: str, severity: str, detail: str) -> None:
        incidents.append({"code": code, "severity": severity, "detail": detail})

    loop_seconds = _loop_seconds(environment)
    if loop_seconds is None:
        heartbeat_stale_seconds = MIN_HEARTBEAT_STALE_SECONDS
        cycle_stale_seconds = MIN_CYCLE_STALE_SECONDS
        startup_grace_seconds = MIN_STARTUP_GRACE_SECONDS
    else:
        heartbeat_stale_seconds = max(MIN_HEARTBEAT_STALE_SECONDS, (2 * loop_seconds) + 30)
        cycle_stale_seconds = max(MIN_CYCLE_STALE_SECONDS, (3 * loop_seconds) + 60)
        startup_grace_seconds = max(MIN_STARTUP_GRACE_SECONDS, 2 * loop_seconds)

    heartbeat_age = _age_seconds(now, status.get("heartbeat_at_utc"))
    last_cycle_age = _age_seconds(now, status.get("last_cycle_finished_at_utc"))
    started_age = _age_seconds(now, status.get("started_at_utc"))

    if not monitor_enabled:
        state = "disabled"
        healthy = False
        incident_active = False
    else:
        if loop_seconds is None:
            incident("invalid_loop_configuration", "critical", "Step 17B loop interval is missing or outside its certified range.")

        if status.get("enabled") is not True:
            incident("step17b_disabled", "critical", "Certified Step 17B runtime is not enabled.")
        if status.get("running") is not True:
            incident("step17b_not_running", "critical", "Certified Step 17B supervisor is not running.")

        role = str(status.get("role") or "")
        leadership = status.get("leadership_acquired") is True
        within_startup_grace = started_age is not None and started_age <= startup_grace_seconds
        if role != "leader" or not leadership:
            if within_startup_grace and role in {"starting", "candidate"}:
                incident("leadership_starting", "warning", "Step 17B is still inside its leadership startup grace window.")
            else:
                incident("leadership_not_held", "critical", "The single production process does not currently hold Step 17B leadership.")

        if heartbeat_age is None:
            incident("heartbeat_missing", "critical", "Step 17B has no parseable runtime heartbeat.")
        elif heartbeat_age > heartbeat_stale_seconds:
            incident("heartbeat_stale", "critical", f"Step 17B heartbeat is {round(heartbeat_age, 3)} seconds old.")

        successes = int(status.get("success_count") or 0)
        failures = int(status.get("failure_count") or 0)
        if successes < 1:
            if within_startup_grace:
                incident("awaiting_first_success", "warning", "Step 17B is still inside the first-cycle startup grace window.")
            else:
                incident("no_successful_cycle", "critical", "Step 17B has not completed a successful durable cycle.")
        else:
            if last_cycle_age is None:
                incident("last_cycle_timestamp_missing", "critical", "Step 17B reports success but no parseable completed-cycle timestamp.")
            elif last_cycle_age > cycle_stale_seconds:
                incident("cycle_stale", "critical", f"Last completed Step 17B cycle is {round(last_cycle_age, 3)} seconds old.")

            version = status.get("last_checkpoint_version")
            if not isinstance(version, int) or isinstance(version, bool) or version <= 0:
                incident("checkpoint_missing", "critical", "Step 17B reports success without a valid durable checkpoint version.")

        if status.get("last_error_class"):
            incident("active_runtime_error", "critical", f"Step 17B currently reports {status.get('last_error_class')}.")
        elif failures > 0:
            incident("historical_runtime_failures", "warning", f"Current Step 17B process has recorded {failures} prior failure(s).")

        duplicate_skips = int(status.get("duplicate_lease_skip_count") or 0)
        if duplicate_skips > 0:
            incident("duplicate_lease_skip_observed", "warning", f"Step 17B has skipped {duplicate_skips} duplicate durable lease attempt(s).")

        leadership_misses = int(status.get("leadership_miss_count") or 0)
        if leadership_misses > 0 and leadership:
            incident("historical_leadership_miss", "warning", f"Current process recorded {leadership_misses} prior leadership miss(es).")

        if status.get("database_secret_exposed") is not False:
            incident("secret_exposure_contract_failed", "critical", "Step 17B secret-exposure safety flag is not false.")
        if status.get("legacy_production_switches_enabled") is not False:
            incident("legacy_switch_contract_failed", "critical", "A frozen legacy production switch is unexpectedly enabled.")
        if status.get("new_render_service_created") is not False:
            incident("render_identity_contract_failed", "critical", "Runtime status does not preserve the single existing Render-service contract.")

        expected_revision = str(environment.get(step17b.STEP17B_EXPECTED_REVISION_ENV) or "").strip().lower()
        deployed_revision = str(environment.get("WNBA_DEPLOYMENT_REVISION") or "").strip().lower()
        if expected_revision and deployed_revision and expected_revision != deployed_revision:
            incident("revision_mismatch", "critical", "Expected and deployed revision identifiers do not match.")

        has_critical = any(item["severity"] == "critical" for item in incidents)
        has_warning = any(item["severity"] == "warning" for item in incidents)
        state = "critical" if has_critical else "degraded" if has_warning else "healthy"
        healthy = not has_critical
        incident_active = bool(incidents)

    return {
        "source": SOURCE,
        "data_type": "wnba_step17c_production_reliability",
        "schema_version": SCHEMA_VERSION,
        "monitor_version": MONITOR_VERSION,
        "generated_at_utc": now.isoformat(),
        "monitor_enabled": monitor_enabled,
        "state": state,
        "healthy": healthy,
        "incident_active": incident_active,
        "incidents": incidents,
        "ages_seconds": {
            "heartbeat": None if heartbeat_age is None else round(heartbeat_age, 3),
            "last_completed_cycle": None if last_cycle_age is None else round(last_cycle_age, 3),
            "process_uptime": None if started_age is None else round(started_age, 3),
        },
        "thresholds_seconds": {
            "heartbeat_stale": heartbeat_stale_seconds,
            "completed_cycle_stale": cycle_stale_seconds,
            "startup_grace": startup_grace_seconds,
            "configured_loop": loop_seconds,
        },
        "step17b": snapshot,
        "semantics": {
            "read_only": True,
            "database_connection_opened": False,
            "database_write_performed": False,
            "scheduler_started": False,
            "scheduler_cycle_triggered": False,
            "sportsbook_network_called": False,
            "model_run": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "database_secret_exposed": False,
            "new_render_service_created": False,
        },
    }


def build_step17c_health(**kwargs: Any) -> dict[str, Any]:
    report = build_step17c_production_reliability(**kwargs)
    return {
        "source": SOURCE,
        "monitor_version": MONITOR_VERSION,
        "status": report["state"],
        "healthy": report["healthy"],
        "incident_active": report["incident_active"],
        "generated_at_utc": report["generated_at_utc"],
        "incidents": report["incidents"],
    }
