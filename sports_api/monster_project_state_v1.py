"""Monster Project State V1 — deterministic, read-only engineering state.

Project State consumes already-normalized Monster packets and reduces them into
one current engineering-state packet. It performs no live network calls and has
no authority to mutate sports logic, source data, runtime, GitHub, Render, or
environment configuration.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PROJECT_STATE_VERSION = "MONSTER_PROJECT_STATE_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_RUNTIME = False
NETWORK_CALLS = False
AUTO_FIX = False
AUTHORITATIVE_MERGE_GATE = "devsystem-final-gate"

_UNSAFE_PRODUCTION_STATES = {
    "DEPLOY_FAILED",
    "RUNTIME_PROOF_FAILED",
    "NOT_READY",
    "IDENTITY_CONFLICT",
    "PRODUCTION_LAG",
    "GUARD_FAILED",
}
_KNOWN_PRODUCTION_STATES = _UNSAFE_PRODUCTION_STATES | {"GREEN", "UNKNOWN"}

_BLOCKED_CONTINUITY_ACTION = "Resolve the recorded blocker before editing."
_BLOCKED_PRODUCTION_ACTION = "Restore Production Certification to GREEN before editing or merging."
_REVALIDATE_ACTION = "Revalidate repository identity and certification evidence before editing."
_UNKNOWN_ACTION = "Supply valid required Project State evidence before continuing."


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _text(value: Any, default: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or default


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value]


def _copy_packet(value: Mapping[str, Any] | None, default: dict[str, Any]) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else dict(default)


def protection_snapshot() -> dict[str, Any]:
    """Return the permanent no-mutation safety contract."""
    return {
        "projection_weight": PROJECTION_WEIGHT,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
        "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
        "may_modify_runtime": MAY_MODIFY_RUNTIME,
        "network_calls": NETWORK_CALLS,
        "auto_fix": AUTO_FIX,
        "authoritative_merge_gate": AUTHORITATIVE_MERGE_GATE,
    }


def _empty_report(
    *,
    production: Mapping[str, Any] | None,
    telemetry: Mapping[str, Any] | None,
    performance: Mapping[str, Any] | None,
    incident: Mapping[str, Any] | None,
    control_plane: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "version": PROJECT_STATE_VERSION,
        "state": "UNKNOWN",
        "current_task": "unknown",
        "current_step": "unknown",
        "completed_steps": [],
        "remaining_steps": [],
        "last_green_evidence": [],
        "repository": {},
        "production": _copy_packet(production, {"status": "UNAVAILABLE"}),
        "telemetry": _copy_packet(telemetry, {"status": "UNAVAILABLE"}),
        "performance": _copy_packet(performance, {"status": "UNAVAILABLE"}),
        "incident": _copy_packet(incident, {"status": "UNAVAILABLE", "blocking": False}),
        "control_plane": _copy_packet(control_plane, {"status": "UNAVAILABLE"}),
        "blockers": [],
        "forbidden_scope": [],
        "next_action": _UNKNOWN_ACTION,
        "reasons": [],
        **protection_snapshot(),
    }


def _continuity_errors(continuity: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    task = _mapping(continuity.get("task"))
    source = _mapping(continuity.get("source"))
    progress = _mapping(continuity.get("progress"))
    scope = _mapping(continuity.get("scope"))

    if task is None:
        errors.append("continuity task packet is missing or malformed")
    else:
        if not _text(task.get("id"), default=""):
            errors.append("continuity task.id is missing")
        if not _text(task.get("title"), default=""):
            errors.append("continuity task.title is missing")
        if not _text(task.get("status"), default=""):
            errors.append("continuity task.status is missing")

    if source is None:
        errors.append("continuity source packet is missing or malformed")
    else:
        for field in ("branch", "commit", "main_commit"):
            if not _text(source.get(field), default=""):
                errors.append(f"continuity source.{field} is missing")

    if progress is None:
        errors.append("continuity progress packet is missing or malformed")
    else:
        if not _text(progress.get("current_step"), default=""):
            errors.append("continuity progress.current_step is missing")
        if not isinstance(progress.get("completed_steps"), list):
            errors.append("continuity progress.completed_steps must be a list")
        if not isinstance(progress.get("remaining_steps"), list):
            errors.append("continuity progress.remaining_steps must be a list")

    if scope is None:
        errors.append("continuity scope packet is missing or malformed")
    elif not isinstance(scope.get("forbidden"), list):
        errors.append("continuity scope.forbidden must be a list")

    if not isinstance(continuity.get("blockers"), list):
        errors.append("continuity blockers must be a list")
    if not isinstance(continuity.get("last_green_evidence"), list):
        errors.append("continuity last_green_evidence must be a list")
    if not _text(continuity.get("next_action"), default=""):
        errors.append("continuity next_action is missing")
    return errors


def _explicit_corruption_reasons(continuity: Mapping[str, Any]) -> list[str]:
    status = _text(continuity.get("status"), default="").upper()
    reasons: list[str] = []
    if continuity.get("tampered") is True or status == "TAMPERED":
        reasons.append("continuity evidence explicitly reports tampering")
    if continuity.get("corrupt") is True or status == "CORRUPT":
        reasons.append("continuity evidence explicitly reports corruption")
    return reasons


def _advisory_reasons(
    *,
    telemetry: Mapping[str, Any] | None,
    performance: Mapping[str, Any] | None,
    control_plane: Mapping[str, Any] | None,
) -> list[str]:
    reasons: list[str] = []
    if telemetry is not None:
        telemetry_status = _text(telemetry.get("status"), default="UNKNOWN").upper()
        if telemetry_status in {"NOT_CONFIGURED", "UNAVAILABLE", "STALE"}:
            reasons.append(f"telemetry advisory: PostHog/Error Radar is {telemetry_status}")

    if performance is not None:
        grade = _text(performance.get("grade"), default="").upper()
        if grade in {"SLOW", "CRITICAL"}:
            reasons.append(f"performance advisory: Monster Performance Profiler grade is {grade}")

    if control_plane is not None:
        status = _text(control_plane.get("status"), default="").upper()
        if status and status not in {"READY", "PASS", "GREEN", "HEALTHY"}:
            reasons.append(f"control-plane advisory: diagnostic status is {status}")
    return reasons


def build_project_state(
    *,
    continuity: Mapping[str, Any] | None,
    production: Mapping[str, Any] | None = None,
    telemetry: Mapping[str, Any] | None = None,
    performance: Mapping[str, Any] | None = None,
    incident: Mapping[str, Any] | None = None,
    control_plane: Mapping[str, Any] | None = None,
    production_required: bool = True,
) -> dict[str, Any]:
    """Build one deterministic project-state packet from normalized evidence."""
    continuity_map = _mapping(continuity)
    production_map = _mapping(production)
    telemetry_map = _mapping(telemetry)
    performance_map = _mapping(performance)
    incident_map = _mapping(incident)
    control_plane_map = _mapping(control_plane)

    report = _empty_report(
        production=production_map,
        telemetry=telemetry_map,
        performance=performance_map,
        incident=incident_map,
        control_plane=control_plane_map,
    )

    if continuity_map is None:
        report["reasons"] = ["required continuity evidence is missing or malformed"]
        return report

    corruption_reasons = _explicit_corruption_reasons(continuity_map)
    continuity_errors = _continuity_errors(continuity_map)

    task = _mapping(continuity_map.get("task")) or {}
    source = _mapping(continuity_map.get("source")) or {}
    progress = _mapping(continuity_map.get("progress")) or {}
    scope = _mapping(continuity_map.get("scope")) or {}
    drift = _mapping(continuity_map.get("drift")) or {}

    report.update(
        {
            "current_task": _text(task.get("title")),
            "current_step": _text(progress.get("current_step")),
            "completed_steps": _string_list(progress.get("completed_steps")),
            "remaining_steps": _string_list(progress.get("remaining_steps")),
            "last_green_evidence": _string_list(continuity_map.get("last_green_evidence")),
            "repository": dict(source),
            "blockers": _string_list(continuity_map.get("blockers")),
            "forbidden_scope": _string_list(scope.get("forbidden")),
            "next_action": _text(continuity_map.get("next_action"), default=_UNKNOWN_ACTION),
        }
    )

    advisory_reasons = _advisory_reasons(
        telemetry=telemetry_map,
        performance=performance_map,
        control_plane=control_plane_map,
    )

    # BLOCKED — explicit corruption/tamper, recorded blocker, blocking incident,
    # or an explicitly unsafe production certification state.
    if corruption_reasons:
        report["state"] = "BLOCKED"
        report["reasons"] = corruption_reasons + advisory_reasons
        report["next_action"] = _BLOCKED_CONTINUITY_ACTION
        return report

    continuity_status = _text(continuity_map.get("status"), default="").upper()
    if report["blockers"] or continuity_status == "BLOCKED":
        report["state"] = "BLOCKED"
        report["reasons"] = ["continuity evidence contains an explicit blocker"] + advisory_reasons
        report["next_action"] = _BLOCKED_CONTINUITY_ACTION
        return report

    incident_status = _text((incident_map or {}).get("status"), default="").upper()
    if incident_map is not None and (
        incident_map.get("blocking") is True or incident_status == "BLOCKED"
    ):
        report["state"] = "BLOCKED"
        report["reasons"] = ["incident evidence explicitly blocks execution"] + advisory_reasons
        report["next_action"] = _text(
            incident_map.get("next_action"), default=_BLOCKED_CONTINUITY_ACTION
        )
        return report

    production_state = ""
    if production_required:
        if production_map is not None:
            production_state = _text(production_map.get("state"), default="").upper()
        if production_state in _UNSAFE_PRODUCTION_STATES:
            report["state"] = "BLOCKED"
            reasons = _string_list(production_map.get("reasons")) if production_map else []
            report["reasons"] = (reasons or [f"production certification is {production_state}"]) + advisory_reasons
            report["next_action"] = _BLOCKED_PRODUCTION_ACTION
            return report
        if production_state == "GREEN" and production_map is not None and production_map.get("certified") is not True:
            report["state"] = "BLOCKED"
            report["reasons"] = [
                "production evidence is contradictory: state is GREEN but certified is not true"
            ] + advisory_reasons
            report["next_action"] = _BLOCKED_PRODUCTION_ACTION
            return report

    # REVALIDATE — repository identity drift is lower precedence than BLOCKED.
    if continuity_status == "REVALIDATE" or drift.get("requires_revalidation") is True:
        report["state"] = "REVALIDATE"
        report["reasons"] = _string_list(drift.get("reasons")) + advisory_reasons
        report["next_action"] = _REVALIDATE_ACTION
        return report

    # UNKNOWN — malformed/missing required evidence is never upgraded optimistically.
    if continuity_errors:
        report["state"] = "UNKNOWN"
        report["reasons"] = continuity_errors + advisory_reasons
        report["next_action"] = _UNKNOWN_ACTION
        return report

    if production_required:
        if production_map is None:
            report["state"] = "UNKNOWN"
            report["reasons"] = ["required production certification evidence is missing"] + advisory_reasons
            report["next_action"] = _UNKNOWN_ACTION
            return report
        if production_state == "UNKNOWN":
            reasons = _string_list(production_map.get("reasons"))
            report["state"] = "UNKNOWN"
            report["reasons"] = (reasons or ["production certification state is UNKNOWN"]) + advisory_reasons
            report["next_action"] = _UNKNOWN_ACTION
            return report
        if production_state not in _KNOWN_PRODUCTION_STATES:
            report["state"] = "UNKNOWN"
            report["reasons"] = [
                f"unrecognized production certification state: {production_state or 'missing'}"
            ] + advisory_reasons
            report["next_action"] = _UNKNOWN_ACTION
            return report
        if production_state != "GREEN" or production_map.get("certified") is not True:
            report["state"] = "UNKNOWN"
            report["reasons"] = ["production certification is not explicitly GREEN"] + advisory_reasons
            report["next_action"] = _UNKNOWN_ACTION
            return report
    elif production_map is None:
        report["production"] = {"status": "NOT_REQUIRED"}

    # COMPLETE, ACTIVE, READY — only after all higher-precedence conditions.
    task_status = _text(task.get("status"), default="").upper()
    if continuity_status == "COMPLETE" or task_status == "COMPLETE":
        report["state"] = "COMPLETE"
        report["reasons"] = advisory_reasons
        return report

    if report["remaining_steps"]:
        report["state"] = "ACTIVE"
        report["reasons"] = advisory_reasons
        return report

    report["state"] = "READY"
    report["reasons"] = advisory_reasons
    return report


__all__ = [
    "AUTHORITATIVE_MERGE_GATE",
    "AUTO_FIX",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RUNTIME",
    "MAY_MODIFY_SOURCE_DATA",
    "NETWORK_CALLS",
    "PROJECT_STATE_VERSION",
    "PROJECTION_WEIGHT",
    "build_project_state",
    "protection_snapshot",
]
