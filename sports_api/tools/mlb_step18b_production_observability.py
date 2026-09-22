"""MLB Step 18B — read-only production observability and SLO classifier.

The monitor observes the certified Step 17B control runtime and Step 18A frozen
rollback baseline. It never opens a database connection, mutates Render, starts a
scheduler, calls a provider/sportsbook, runs projections or Monte Carlo, enables
actionable output, or performs wagering.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

SCHEMA_VERSION = "mlb_step18b_production_observability_v1"
MONITOR_VERSION = "mlb_step18b_read_only_slo_watchdog_v1"
FINAL_MARKER = "MLB_STEP18B_PRODUCTION_OBSERVABILITY_GREEN"
STEP18A_MERGED_MAIN_SHA = "60f8917e4f963f733759f60b82d7dcf468f776cf"
STEP17B_CERTIFIED_DEPLOYED_SHA = "ece3cd2d15d091728fdbe30be774dd9c15e4fe8e"
EXPECTED_MLB_DATA_TYPE = "mlb_step17b_runtime_status_v1"
EXPECTED_WNBA_DATA_TYPE = "wnba_deployment_and_smoke_readiness"
CERTIFIED_LOOP_SECONDS = 60
MIN_HEARTBEAT_STALE_SECONDS = 120
MIN_CYCLE_STALE_SECONDS = 180
MIN_STARTUP_GRACE_SECONDS = 120


class MLBStep18BObservabilityError(RuntimeError):
    """Raised only for malformed monitor inputs, never to mutate production."""


def _utc(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise MLBStep18BObservabilityError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MLBStep18BObservabilityError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


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


def _safe_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _sanitized_status(status: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "data_type",
        "schema_version",
        "runtime_version",
        "contract_id",
        "runtime_mode",
        "enabled",
        "running",
        "role",
        "leadership_acquired",
        "started_at_utc",
        "heartbeat_at_utc",
        "next_cycle_due_at_utc",
        "control_cycle_count",
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
        "provider_workload_cycle_count",
        "sportsbook_workload_cycle_count",
        "production_scheduler_started",
        "legacy_production_runtime_started",
        "actionable_output_enabled",
        "wagering_enabled",
        "provider_calls",
        "sportsbook_calls",
        "database_secret_exposed",
        "new_render_service_created",
    )
    return {key: deepcopy(status.get(key)) for key in allowed}


def build_production_observability(
    *,
    status: Mapping[str, Any],
    health: Mapping[str, Any] | None = None,
    wnba: Mapping[str, Any] | None = None,
    now_utc: datetime | str | None = None,
    configured_loop_seconds: int = CERTIFIED_LOOP_SECONDS,
) -> dict[str, Any]:
    """Classify live production health from already-sanitized GET responses."""
    if not isinstance(status, Mapping):
        raise MLBStep18BObservabilityError("Step 18B requires an MLB status object")
    if isinstance(configured_loop_seconds, bool) or not isinstance(configured_loop_seconds, int):
        raise MLBStep18BObservabilityError("configured loop seconds must be an integer")
    if not 30 <= configured_loop_seconds <= 3600:
        raise MLBStep18BObservabilityError("configured loop seconds outside certified range")

    now = _utc(now_utc)
    heartbeat_stale = max(MIN_HEARTBEAT_STALE_SECONDS, (2 * configured_loop_seconds) + 30)
    cycle_stale = max(MIN_CYCLE_STALE_SECONDS, (3 * configured_loop_seconds) + 60)
    startup_grace = max(MIN_STARTUP_GRACE_SECONDS, 2 * configured_loop_seconds)
    heartbeat_age = _age_seconds(now, status.get("heartbeat_at_utc"))
    cycle_age = _age_seconds(now, status.get("last_cycle_finished_at_utc"))
    uptime = _age_seconds(now, status.get("started_at_utc"))
    within_startup_grace = uptime is not None and uptime <= startup_grace

    incidents: list[dict[str, str]] = []

    def incident(code: str, severity: str, detail: str) -> None:
        incidents.append({"code": code, "severity": severity, "detail": detail})

    if status.get("data_type") != EXPECTED_MLB_DATA_TYPE:
        incident("mlb_status_contract_drift", "critical", "Hosted MLB Step 17B status contract drifted.")
    if status.get("enabled") is not True:
        incident("step17b_disabled", "critical", "Certified MLB Step 17B runtime is not enabled.")
    if status.get("running") is not True:
        incident("step17b_not_running", "critical", "Certified MLB Step 17B runtime is not running.")

    role = str(status.get("role") or "")
    leadership = status.get("leadership_acquired") is True
    if role != "leader" or not leadership:
        if within_startup_grace and role in {"starting", "candidate"}:
            incident("leadership_starting", "warning", "Runtime is inside the certified startup grace window.")
        else:
            incident("leadership_not_held", "critical", "The production process does not currently hold Step 17B leadership.")

    if heartbeat_age is None:
        incident("heartbeat_missing", "critical", "No parseable Step 17B heartbeat is available.")
    elif heartbeat_age > heartbeat_stale:
        incident("heartbeat_stale", "critical", f"Step 17B heartbeat is {round(heartbeat_age, 3)} seconds old.")

    successes = _safe_int(status.get("success_count"))
    failures = _safe_int(status.get("failure_count"))
    if successes < 1:
        if within_startup_grace:
            incident("awaiting_first_success", "warning", "Runtime is inside first-cycle startup grace.")
        else:
            incident("no_successful_cycle", "critical", "No successful durable control cycle has completed.")
    else:
        if cycle_age is None:
            incident("cycle_timestamp_missing", "critical", "Success is reported without a completed-cycle timestamp.")
        elif cycle_age > cycle_stale:
            incident("cycle_stale", "critical", f"Last completed cycle is {round(cycle_age, 3)} seconds old.")
        checkpoint = status.get("last_checkpoint_version")
        if isinstance(checkpoint, bool) or not isinstance(checkpoint, int) or checkpoint <= 0:
            incident("checkpoint_missing", "critical", "Durable checkpoint version is unavailable.")
        if status.get("recovered_from_checkpoint") is not True:
            incident("restart_recovery_not_proven", "critical", "Live process does not prove durable checkpoint recovery.")

    if status.get("last_error_class"):
        incident("active_runtime_error", "critical", f"Live runtime reports {status.get('last_error_class')}.")
    elif failures > 0:
        incident("historical_runtime_failures", "warning", f"Current process recorded {failures} prior runtime failure(s).")

    duplicate_skips = _safe_int(status.get("duplicate_lease_skip_count"))
    if duplicate_skips > 0:
        incident("duplicate_lease_skip_observed", "warning", f"Runtime recorded {duplicate_skips} duplicate lease skip(s).")

    if _safe_int(status.get("provider_calls")) != 0 or _safe_int(status.get("provider_workload_cycle_count")) != 0:
        incident("provider_boundary_crossed", "critical", "Step 17B provider workload/call boundary was crossed.")
    if _safe_int(status.get("sportsbook_calls")) != 0 or _safe_int(status.get("sportsbook_workload_cycle_count")) != 0:
        incident("sportsbook_boundary_crossed", "critical", "Step 17B sportsbook workload/call boundary was crossed.")
    if status.get("production_scheduler_started") is not False:
        incident("legacy_scheduler_started", "critical", "Frozen legacy MLB production scheduler started.")
    if status.get("legacy_production_runtime_started") is not False:
        incident("legacy_runtime_started", "critical", "Frozen legacy MLB production runtime started.")
    if status.get("actionable_output_enabled") is not False:
        incident("actionable_output_enabled", "critical", "Actionable MLB output is unexpectedly enabled.")
    if status.get("wagering_enabled") is not False:
        incident("wagering_enabled", "critical", "MLB wagering is unexpectedly enabled.")
    if status.get("database_secret_exposed") is not False:
        incident("database_secret_contract_failed", "critical", "Database secret-exposure flag is not false.")
    if status.get("new_render_service_created") is not False:
        incident("render_identity_contract_failed", "critical", "Single shared Render-service contract drifted.")

    if health is not None:
        if not isinstance(health, Mapping) or health.get("status") != "ok":
            incident("host_health_failed", "critical", "Shared production host /health is not OK.")

    if wnba is not None:
        if not isinstance(wnba, Mapping) or wnba.get("data_type") != EXPECTED_WNBA_DATA_TYPE:
            incident("wnba_continuity_contract_drift", "critical", "WNBA deployment contract drifted on the shared host.")
        else:
            semantics = wnba.get("semantics") if isinstance(wnba.get("semantics"), Mapping) else {}
            if semantics.get("deployment_gate_does_not_call_sportsbook") is not True:
                incident("wnba_sportsbook_safety_drift", "critical", "WNBA deployment sportsbook safety contract drifted.")
            if semantics.get("deployment_gate_does_not_run_monte_carlo") is not True:
                incident("wnba_monte_carlo_safety_drift", "critical", "WNBA deployment Monte Carlo safety contract drifted.")
            if semantics.get("live_smoke_is_read_only") is not True:
                incident("wnba_read_only_safety_drift", "critical", "WNBA live smoke is no longer read-only.")

    has_critical = any(item["severity"] == "critical" for item in incidents)
    has_warning = any(item["severity"] == "warning" for item in incidents)
    state = "critical" if has_critical else "degraded" if has_warning else "healthy"
    report = {
        "data_type": "mlb_step18b_production_observability",
        "schema_version": SCHEMA_VERSION,
        "monitor_version": MONITOR_VERSION,
        "generated_at_utc": now.isoformat(),
        "state": state,
        "healthy": not has_critical,
        "incident_active": bool(incidents),
        "critical_incident_count": sum(item["severity"] == "critical" for item in incidents),
        "warning_incident_count": sum(item["severity"] == "warning" for item in incidents),
        "incidents": incidents,
        "ages_seconds": {
            "heartbeat": None if heartbeat_age is None else round(heartbeat_age, 3),
            "last_completed_cycle": None if cycle_age is None else round(cycle_age, 3),
            "process_uptime": None if uptime is None else round(uptime, 3),
        },
        "thresholds_seconds": {
            "configured_loop": configured_loop_seconds,
            "heartbeat_stale": heartbeat_stale,
            "completed_cycle_stale": cycle_stale,
            "startup_grace": startup_grace,
        },
        "lineage": {
            "step18a_merged_main_sha": STEP18A_MERGED_MAIN_SHA,
            "step17b_certified_deployed_sha": STEP17B_CERTIFIED_DEPLOYED_SHA,
        },
        "mlb_step17b": _sanitized_status(status),
        "shared_host": {
            "health_ok": None if health is None else bool(isinstance(health, Mapping) and health.get("status") == "ok"),
            "wnba_continuity_ok": None if wnba is None else not any(item["code"].startswith("wnba_") for item in incidents),
        },
        "semantics": {
            "read_only": True,
            "render_mutation_performed": False,
            "database_connection_opened": False,
            "database_read_performed": False,
            "database_write_performed": False,
            "scheduler_started": False,
            "scheduler_cycle_triggered": False,
            "provider_network_called": False,
            "sportsbook_network_called": False,
            "model_run": False,
            "projection_run": False,
            "monte_carlo_run": False,
            "actionable_output_enabled": False,
            "wager_action_performed": False,
            "database_secret_exposed": False,
            "new_render_service_created": False,
        },
    }
    report["report_sha256"] = _canonical_hash(
        {key: deepcopy(value) for key, value in report.items() if key != "generated_at_utc"}
    )
    return report


__all__ = [
    "CERTIFIED_LOOP_SECONDS",
    "FINAL_MARKER",
    "MLBStep18BObservabilityError",
    "MONITOR_VERSION",
    "SCHEMA_VERSION",
    "STEP17B_CERTIFIED_DEPLOYED_SHA",
    "STEP18A_MERGED_MAIN_SHA",
    "build_production_observability",
]
