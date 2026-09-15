"""Monster Project State V1 — deterministic, read-only engineering state.

This module classifies already-normalized Monster evidence. It performs no live
network calls and has no authority to mutate sports logic, source data, runtime,
GitHub, Render, or environment configuration.
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

_BLOCKED_CONTINUITY_ACTION = "Resolve the recorded blocker before editing."
_BLOCKED_PRODUCTION_ACTION = "Restore Production Certification to GREEN before editing or merging."
_UNKNOWN_ACTION = "Supply valid required Project State evidence before continuing."


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _text(value: Any, default: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or default


def protection_snapshot() -> dict[str, Any]:
    return {
        "projection_weight": PROJECTION_WEIGHT,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
        "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
        "may_modify_runtime": MAY_MODIFY_RUNTIME,
        "network_calls": NETWORK_CALLS,
        "auto_fix": AUTO_FIX,
        "authoritative_merge_gate": AUTHORITATIVE_MERGE_GATE,
    }


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

    if continuity_map is None:
        return {
            "version": PROJECT_STATE_VERSION,
            "state": "UNKNOWN",
            "current_task": "unknown",
            "current_step": "unknown",
            "blockers": [],
            "next_action": _UNKNOWN_ACTION,
            **protection_snapshot(),
        }

    task = _mapping(continuity_map.get("task")) or {}
    source = _mapping(continuity_map.get("source")) or {}
    progress = _mapping(continuity_map.get("progress")) or {}
    scope = _mapping(continuity_map.get("scope")) or {}
    blockers = [str(item) for item in _list(continuity_map.get("blockers"))]

    report = {
        "version": PROJECT_STATE_VERSION,
        "state": "ACTIVE",
        "current_task": _text(task.get("title")),
        "current_step": _text(progress.get("current_step")),
        "completed_steps": [str(item) for item in _list(progress.get("completed_steps"))],
        "remaining_steps": [str(item) for item in _list(progress.get("remaining_steps"))],
        "last_green_evidence": [str(item) for item in _list(continuity_map.get("last_green_evidence"))],
        "repository": dict(source),
        "production": dict(production_map or {}),
        "telemetry": dict(_mapping(telemetry) or {"status": "UNAVAILABLE"}),
        "performance": dict(_mapping(performance) or {"status": "UNAVAILABLE"}),
        "incident": dict(_mapping(incident) or {"status": "UNAVAILABLE", "blocking": False}),
        "control_plane": dict(_mapping(control_plane) or {"status": "UNAVAILABLE"}),
        "blockers": blockers,
        "forbidden_scope": [str(item) for item in _list(scope.get("forbidden"))],
        "next_action": _text(continuity_map.get("next_action"), default=_UNKNOWN_ACTION),
        "reasons": [],
        **protection_snapshot(),
    }

    continuity_status = _text(continuity_map.get("status"), default="").upper()
    if blockers or continuity_status == "BLOCKED":
        report["state"] = "BLOCKED"
        report["next_action"] = _BLOCKED_CONTINUITY_ACTION
        return report

    if production_required:
        if production_map is None:
            report["state"] = "UNKNOWN"
            report["next_action"] = _UNKNOWN_ACTION
            return report
        production_state = _text(production_map.get("state"), default="").upper()
        if production_state in _UNSAFE_PRODUCTION_STATES:
            report["state"] = "BLOCKED"
            report["reasons"] = [str(item) for item in _list(production_map.get("reasons"))]
            report["next_action"] = _BLOCKED_PRODUCTION_ACTION
            return report

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
