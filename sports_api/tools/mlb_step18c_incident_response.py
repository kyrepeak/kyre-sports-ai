"""MLB Step 18C — fail-closed incident response and manual rollback planner.

Consumes a sanitized Step 18B observability report and emits an operator plan.
This layer is intentionally advisory: it never mutates Render, GitHub, databases,
runtime flags, schedulers, providers, sportsbooks, models, projections, or wagers.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any

SCHEMA_VERSION = "mlb_step18c_incident_response_v1"
PLANNER_VERSION = "mlb_step18c_manual_recovery_planner_v1"
FINAL_MARKER = "MLB_STEP18C_INCIDENT_RESPONSE_GREEN"
STEP18B_MERGED_MAIN_SHA = "ae66134026297516aac4e6936b8ac9d8e2302481"
CERTIFIED_RENDER_ROLLBACK_REVISION = "ece3cd2d15d091728fdbe30be774dd9c15e4fe8e"
EXPECTED_REPORT_DATA_TYPE = "mlb_step18b_production_observability"

SAFETY_BOUNDARY_CODES = frozenset(
    {
        "provider_boundary_crossed",
        "sportsbook_boundary_crossed",
        "legacy_scheduler_started",
        "legacy_runtime_started",
        "actionable_output_enabled",
        "wagering_enabled",
        "database_secret_contract_failed",
        "render_identity_contract_failed",
        "wnba_sportsbook_safety_drift",
        "wnba_monte_carlo_safety_drift",
        "wnba_read_only_safety_drift",
    }
)

ROLLBACK_RECOMMENDED_CODES = SAFETY_BOUNDARY_CODES | frozenset(
    {
        "mlb_status_contract_drift",
        "step17b_disabled",
        "step17b_not_running",
        "restart_recovery_not_proven",
        "checkpoint_missing",
        "wnba_continuity_contract_drift",
    }
)

INVESTIGATE_FIRST_CODES = frozenset(
    {
        "heartbeat_missing",
        "heartbeat_stale",
        "cycle_timestamp_missing",
        "cycle_stale",
        "leadership_not_held",
        "active_runtime_error",
        "host_health_failed",
    }
)


class MLBStep18CIncidentResponseError(RuntimeError):
    """Raised for malformed or unsupported Step 18B reports."""


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


def _incident_rows(report: Mapping[str, Any]) -> list[dict[str, str]]:
    raw = report.get("incidents")
    if not isinstance(raw, list):
        raise MLBStep18CIncidentResponseError("Step 18B incidents must be a list")
    rows: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise MLBStep18CIncidentResponseError("Step 18B incident row must be an object")
        code = str(item.get("code") or "").strip()
        severity = str(item.get("severity") or "").strip().casefold()
        detail = str(item.get("detail") or "").strip()
        if not code or severity not in {"warning", "critical"}:
            raise MLBStep18CIncidentResponseError("Step 18B incident row is malformed")
        rows.append({"code": code, "severity": severity, "detail": detail})
    return rows


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def build_incident_response_plan(report: Mapping[str, Any]) -> dict[str, Any]:
    """Translate a sanitized Step 18B report into a manual, fail-closed response plan."""
    if not isinstance(report, Mapping):
        raise MLBStep18CIncidentResponseError("Step 18C requires a Step 18B report object")
    if report.get("data_type") != EXPECTED_REPORT_DATA_TYPE:
        raise MLBStep18CIncidentResponseError("unsupported observability report contract")

    incidents = _incident_rows(report)
    critical_codes = [row["code"] for row in incidents if row["severity"] == "critical"]
    warning_codes = [row["code"] for row in incidents if row["severity"] == "warning"]
    safety_codes = [code for code in critical_codes if code in SAFETY_BOUNDARY_CODES]
    rollback_codes = [code for code in critical_codes if code in ROLLBACK_RECOMMENDED_CODES]
    investigate_codes = [code for code in critical_codes if code in INVESTIGATE_FIRST_CODES]

    if critical_codes:
        response_state = "critical"
        page_operator = True
        if rollback_codes:
            disposition = "manual_rollback_recommended"
            rollback_recommended = True
        else:
            disposition = "manual_investigation_required"
            rollback_recommended = False
    elif warning_codes:
        response_state = "degraded"
        page_operator = False
        disposition = "observe_and_collect_evidence"
        rollback_recommended = False
    else:
        response_state = "healthy"
        page_operator = False
        disposition = "no_action"
        rollback_recommended = False

    actions: list[str] = []
    if response_state == "healthy":
        actions.append("No operator action required; preserve the certified production state.")
    elif response_state == "degraded":
        actions.extend(
            [
                "Preserve the current production state; do not change runtime flags or deployment revision.",
                "Capture the current Step 18B evidence and compare the next observation before escalating.",
            ]
        )
    else:
        actions.append("Freeze discretionary production changes and preserve current evidence before intervention.")
        if safety_codes:
            actions.append("Treat the incident as a safety-boundary breach; do not enable provider, sportsbook, actionable-output, wagering, or legacy runtime paths.")
        if investigate_codes:
            actions.append("Inspect hosted health, leadership, heartbeat, durable checkpoint and current error state before deciding whether a restart is sufficient.")
        if rollback_recommended:
            actions.append(f"Prepare a manual rollback to certified deployed revision {CERTIFIED_RENDER_ROLLBACK_REVISION}; do not execute automatically.")
        else:
            actions.append("Do not roll back automatically; require operator review of the incident evidence first.")
        actions.append("After any manual recovery action, rerun the Step 18A baseline and Step 18B observability gates before declaring recovery.")

    source_summary = {
        "state": report.get("state"),
        "healthy": report.get("healthy"),
        "critical_incident_count": report.get("critical_incident_count"),
        "warning_incident_count": report.get("warning_incident_count"),
        "report_sha256": report.get("report_sha256"),
        "ages_seconds": deepcopy(report.get("ages_seconds")),
        "thresholds_seconds": deepcopy(report.get("thresholds_seconds")),
    }
    plan = {
        "data_type": "mlb_step18c_incident_response_plan",
        "schema_version": SCHEMA_VERSION,
        "planner_version": PLANNER_VERSION,
        "response_state": response_state,
        "disposition": disposition,
        "page_operator": page_operator,
        "rollback_recommended": rollback_recommended,
        "automatic_rollback_performed": False,
        "critical_codes": _dedupe(critical_codes),
        "warning_codes": _dedupe(warning_codes),
        "safety_boundary_codes": _dedupe(safety_codes),
        "investigate_first_codes": _dedupe(investigate_codes),
        "operator_actions": actions,
        "rollback_target": {
            "revision": CERTIFIED_RENDER_ROLLBACK_REVISION,
            "execution_mode": "manual_only",
            "requires_post_recovery_step18a": True,
            "requires_post_recovery_step18b": True,
        },
        "lineage": {
            "step18b_merged_main_sha": STEP18B_MERGED_MAIN_SHA,
            "certified_render_rollback_revision": CERTIFIED_RENDER_ROLLBACK_REVISION,
        },
        "source_observability": source_summary,
        "semantics": {
            "advisory_only": True,
            "render_mutation_performed": False,
            "github_mutation_performed": False,
            "database_connection_opened": False,
            "database_read_performed": False,
            "database_write_performed": False,
            "scheduler_started": False,
            "provider_network_called": False,
            "sportsbook_network_called": False,
            "model_run": False,
            "projection_run": False,
            "monte_carlo_run": False,
            "actionable_output_enabled": False,
            "wager_action_performed": False,
        },
    }
    plan["plan_sha256"] = _canonical_hash(plan)
    return plan


__all__ = [
    "CERTIFIED_RENDER_ROLLBACK_REVISION",
    "FINAL_MARKER",
    "MLBStep18CIncidentResponseError",
    "PLANNER_VERSION",
    "ROLLBACK_RECOMMENDED_CODES",
    "SAFETY_BOUNDARY_CODES",
    "SCHEMA_VERSION",
    "STEP18B_MERGED_MAIN_SHA",
    "build_incident_response_plan",
]
