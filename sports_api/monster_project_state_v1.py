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

_CONTINUITY_VERSION = "MONSTER_CONTINUITY_V1"
_CONTINUITY_RESUME_STATES = {"READY_TO_RESUME", "REVALIDATE", "BLOCKED", "COMPLETE"}
_CONTINUITY_TASK_STATES = {"ACTIVE", "BLOCKED", "READY_TO_MERGE", "COMPLETE"}
_CONTINUITY_STEP_STATES = {"PENDING", "IN_PROGRESS", "BLOCKED", "GREEN", "COMPLETE"}
_PRODUCTION_VERSION = "MONSTER_PRODUCTION_CERTIFICATION_V1"

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

    if continuity.get("version") != _CONTINUITY_VERSION:
        errors.append("continuity version is missing or unsupported")

    continuity_status = _text(continuity.get("status"), default="").upper()
    if continuity_status not in _CONTINUITY_RESUME_STATES:
        errors.append("continuity status is missing or invalid")

    if task is None:
        errors.append("continuity task packet is missing or malformed")
    else:
        if not _text(task.get("id"), default=""):
            errors.append("continuity task.id is missing")
        if not _text(task.get("title"), default=""):
            errors.append("continuity task.title is missing")
        task_status = _text(task.get("status"), default="").upper()
        if task_status not in _CONTINUITY_TASK_STATES:
            errors.append("continuity task.status is missing or invalid")

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
        step_status = _text(progress.get("step_status"), default="").upper()
        if step_status not in _CONTINUITY_STEP_STATES:
            errors.append("continuity progress.step_status is missing or invalid")
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


def _production_errors(production: Mapping[str, Any]) -> list[str]:
    """Validate the stable evidence shape emitted by Production Certification V1."""
    errors: list[str] = []
    identity = _mapping(production.get("identity"))
    readiness = _mapping(production.get("readiness"))
    guards = _mapping(production.get("guards"))

    if production.get("version") != _PRODUCTION_VERSION:
        errors.append("production certification version is missing or unsupported")

    if not isinstance(production.get("certified"), bool):
        errors.append("production certification certified must be boolean")

    if identity is None:
        errors.append("production certification identity packet is missing or malformed")
    else:
        for field in (
            "github_branch",
            "github_commit",
            "render_branch",
            "render_commit",
            "health_branch",
            "health_commit",
        ):
            if not _text(identity.get(field), default=""):
                errors.append(f"production certification identity.{field} is missing")

    for field in ("render_status", "render_auto_deploy", "health_status"):
        if not _text(production.get(field), default=""):
            errors.append(f"production certification {field} is missing")

    if readiness is None:
        errors.append("production certification readiness packet is missing or malformed")
    else:
        if not _text(readiness.get("status"), default=""):
            errors.append("production certification readiness.status is missing")
        checks = _mapping(readiness.get("checks"))
        if checks is None:
            errors.append("production certification readiness.checks is missing or malformed")
        else:
            for field in (
                "process_running",
                "python_runtime",
                "deployment_identity_available",
                "runtime_branch_alignment",
            ):
                if not isinstance(checks.get(field), bool):
                    errors.append(
                        f"production certification readiness.checks.{field} must be boolean"
                    )
        if not isinstance(readiness.get("deployment_aligned"), bool):
            errors.append("production certification readiness.deployment_aligned must be boolean")

    if guards is None:
        errors.append("production certification guards packet is missing or malformed")
    else:
        for field in ("devsystem-final-gate", "permanent-freeze", "regression-shield"):
            if not _text(guards.get(field), default=""):
                errors.append(f"production certification guard {field} is missing")

    if not isinstance(production.get("reasons"), list):
        errors.append("production certification reasons must be a list")
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
    production_errors: list[str] = []
    if production_required:
        if production_map is not None:
            production_state = _text(production_map.get("state"), default="").upper()
            production_errors = _production_errors(production_map)
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
        if production_errors:
            report["state"] = "UNKNOWN"
            report["reasons"] = production_errors + advisory_reasons
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


# ---------------------------------------------------------------------------
# MONSTER V8 Step 4 — Unified Proof Bundle
# ---------------------------------------------------------------------------

import hashlib as _bundle_hashlib
import json as _bundle_json
import re as _bundle_re

UNIFIED_PROOF_BUNDLE_VERSION = "MONSTER_V8_UNIFIED_PROOF_BUNDLE_V1"

_BUNDLE_SHA40 = _bundle_re.compile(r"^[0-9a-f]{40}$")
_BUNDLE_HASH64 = _bundle_re.compile(r"^[0-9a-f]{64}$")


class UnifiedProofBundleError(ValueError):
    """Raised when unified certification evidence is incomplete or inconsistent."""


def _bundle_canonical(value: Any) -> str:
    return _bundle_json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _bundle_sha256(value: Any) -> str:
    return _bundle_hashlib.sha256(
        _bundle_canonical(value).encode("utf-8")
    ).hexdigest()


def _bundle_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise UnifiedProofBundleError(f"{field} is required")
    return text


def _bundle_sha(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _BUNDLE_SHA40.fullmatch(text):
        raise UnifiedProofBundleError(f"{field} must be a full git SHA")
    return text


def _bundle_hash64(value: Any, field: str, *, prefixed: bool) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("sha256:"):
        text = text[7:]
    if not _BUNDLE_HASH64.fullmatch(text):
        raise UnifiedProofBundleError(f"{field} must be sha256")
    return f"sha256:{text}" if prefixed else text


def _bundle_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    if not text or text.startswith("/") or ".." in text.split("/"):
        raise UnifiedProofBundleError("artifact/dependency path must be repository-relative")
    return text


def _bundle_blob_map(value: Any, field: str, *, require_nonempty: bool) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise UnifiedProofBundleError(f"{field} must be an object")
    normalized: dict[str, str] = {}
    for raw_path, raw_blob in value.items():
        path = _bundle_path(raw_path)
        if path in normalized:
            raise UnifiedProofBundleError(f"duplicate {field} path: {path}")
        normalized[path] = _bundle_sha(raw_blob, f"{field}[{path}]")
    if require_nonempty and not normalized:
        raise UnifiedProofBundleError(f"{field} cannot be empty")
    return dict(sorted(normalized.items()))


def _bundle_run(
    value: Any,
    *,
    field: str,
    proof_head_sha: str,
    require_test_count: bool,
    require_final_gate: bool,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise UnifiedProofBundleError(f"{field} must be an object")
    try:
        run_id = int(value.get("run_id"))
    except (TypeError, ValueError) as exc:
        raise UnifiedProofBundleError(f"{field}.run_id must be positive") from exc
    if run_id <= 0:
        raise UnifiedProofBundleError(f"{field}.run_id must be positive")
    head_sha = _bundle_sha(value.get("head_sha"), f"{field}.head_sha")
    if head_sha != proof_head_sha:
        raise UnifiedProofBundleError(f"{field}.head_sha mismatch")
    conclusion = _bundle_text(value.get("conclusion"), f"{field}.conclusion").lower()
    if conclusion != "success":
        raise UnifiedProofBundleError(f"{field} must be successful")
    result: dict[str, Any] = {
        "run_id": run_id,
        "head_sha": head_sha,
        "conclusion": conclusion,
    }
    if require_test_count:
        try:
            test_count = int(value.get("test_count"))
        except (TypeError, ValueError) as exc:
            raise UnifiedProofBundleError(
                f"{field}.test_count must be positive"
            ) from exc
        if test_count <= 0:
            raise UnifiedProofBundleError(f"{field}.test_count must be positive")
        result["test_count"] = test_count
    if require_final_gate:
        final_gate = _bundle_text(
            value.get("final_gate"),
            f"{field}.final_gate",
        ).lower()
        if final_gate != "success":
            raise UnifiedProofBundleError(f"{field}.final_gate must be success")
        result["final_gate"] = final_gate
    return result


def _bundle_terminal_receipt(
    value: Any,
    *,
    proof_head_sha: str,
    devsystem_run_id: int,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise UnifiedProofBundleError("terminal_receipt must be an object")
    try:
        run_id = int(value.get("run_id"))
        artifact_id = int(value.get("artifact_id"))
    except (TypeError, ValueError) as exc:
        raise UnifiedProofBundleError(
            "terminal_receipt run_id/artifact_id must be positive"
        ) from exc
    if run_id <= 0 or artifact_id <= 0:
        raise UnifiedProofBundleError(
            "terminal_receipt run_id/artifact_id must be positive"
        )
    if run_id != devsystem_run_id:
        raise UnifiedProofBundleError(
            "terminal_receipt.run_id must match devsystem proof run"
        )
    head_sha = _bundle_sha(value.get("head_sha"), "terminal_receipt.head_sha")
    if head_sha != proof_head_sha:
        raise UnifiedProofBundleError("terminal_receipt.head_sha mismatch")
    return {
        "run_id": run_id,
        "head_sha": head_sha,
        "receipt_hash": _bundle_hash64(
            value.get("receipt_hash"),
            "terminal_receipt.receipt_hash",
            prefixed=True,
        ),
        "artifact_id": artifact_id,
        "artifact_zip_sha256": _bundle_hash64(
            value.get("artifact_zip_sha256"),
            "terminal_receipt.artifact_zip_sha256",
            prefixed=False,
        ),
    }


def _bundle_deployment(value: Any, *, merged_main_sha: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise UnifiedProofBundleError("deployment must be an object")
    required = bool(value.get("required"))
    status = _bundle_text(value.get("status"), "deployment.status").upper()
    if not required:
        if status != "NOT_REQUIRED":
            raise UnifiedProofBundleError(
                "non-required deployment must use NOT_REQUIRED status"
            )
        return {
            "required": False,
            "status": "NOT_REQUIRED",
            "certified": False,
        }

    if status != "GREEN" or value.get("certified") is not True:
        raise UnifiedProofBundleError(
            "required deployment must be GREEN and certified"
        )
    certified_sha = _bundle_sha(
        value.get("certified_sha"),
        "deployment.certified_sha",
    )
    if certified_sha != merged_main_sha:
        raise UnifiedProofBundleError("deployment.certified_sha mismatch")
    return {
        "required": True,
        "status": "GREEN",
        "certified": True,
        "certified_sha": certified_sha,
        "receipt_digest": _bundle_hash64(
            value.get("receipt_digest"),
            "deployment.receipt_digest",
            prefixed=True,
        ),
    }


def _bundle_lineage(value: Any, *, checkpoint_id: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise UnifiedProofBundleError("lineage must be an object")
    observed_checkpoint = _bundle_text(
        value.get("checkpoint_id"),
        "lineage.checkpoint_id",
    )
    if observed_checkpoint != checkpoint_id:
        raise UnifiedProofBundleError("lineage.checkpoint_id mismatch")
    try:
        writer_count = int(value.get("writer_count"))
        consumer_count = int(value.get("consumer_count"))
    except (TypeError, ValueError) as exc:
        raise UnifiedProofBundleError(
            "lineage writer_count/consumer_count must be integers"
        ) from exc
    if writer_count <= 0 or consumer_count < 0:
        raise UnifiedProofBundleError(
            "lineage requires at least one writer and non-negative consumers"
        )
    return {
        "checkpoint_id": checkpoint_id,
        "root_event_id": _bundle_text(
            value.get("root_event_id"),
            "lineage.root_event_id",
        ),
        "lineage_digest": _bundle_hash64(
            value.get("lineage_digest"),
            "lineage.lineage_digest",
            prefixed=True,
        ),
        "writer_count": writer_count,
        "consumer_count": consumer_count,
    }


def _bundle_regression_debt(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise UnifiedProofBundleError("regression_debt must be an object")
    state = _bundle_text(
        value.get("state"),
        "regression_debt.state",
    ).upper()
    if state != "CLEARED":
        raise UnifiedProofBundleError("regression debt must be CLEARED")
    return {
        "state": "CLEARED",
        "permanent_test": _bundle_path(value.get("permanent_test")),
    }


def _bundle_freeze_receipt(
    value: Any,
    *,
    checkpoint_id: str,
    merged_main_sha: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise UnifiedProofBundleError("freeze_receipt must be an object")
    status = _bundle_text(value.get("status"), "freeze_receipt.status").upper()
    if status != "FROZEN":
        raise UnifiedProofBundleError("freeze_receipt must be FROZEN")
    observed_checkpoint = _bundle_text(
        value.get("checkpoint_id"),
        "freeze_receipt.checkpoint_id",
    )
    if observed_checkpoint != checkpoint_id:
        raise UnifiedProofBundleError("freeze_receipt.checkpoint_id mismatch")
    source_main_sha = _bundle_sha(
        value.get("source_main_sha"),
        "freeze_receipt.source_main_sha",
    )
    if source_main_sha != merged_main_sha:
        raise UnifiedProofBundleError("freeze_receipt.source_main_sha mismatch")
    try:
        revision = int(value.get("registry_revision"))
    except (TypeError, ValueError) as exc:
        raise UnifiedProofBundleError(
            "freeze_receipt.registry_revision must be positive"
        ) from exc
    if revision <= 0:
        raise UnifiedProofBundleError(
            "freeze_receipt.registry_revision must be positive"
        )
    result = {
        "status": "FROZEN",
        "checkpoint_id": checkpoint_id,
        "source_main_sha": source_main_sha,
        "registry_revision": revision,
        "registry_state_hash": _bundle_hash64(
            value.get("registry_state_hash"),
            "freeze_receipt.registry_state_hash",
            prefixed=False,
        ),
    }
    if value.get("freeze_commit_sha") is not None:
        result["freeze_commit_sha"] = _bundle_sha(
            value.get("freeze_commit_sha"),
            "freeze_receipt.freeze_commit_sha",
        )
    return result


def _bundle_proof_reuse(
    value: Any,
    *,
    proof_head_sha: str,
    merged_main_sha: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise UnifiedProofBundleError("proof_reuse must be an object")
    decision = _bundle_text(
        value.get("decision"),
        "proof_reuse.decision",
    ).upper()

    if proof_head_sha == merged_main_sha:
        if decision != "NOT_REQUIRED":
            raise UnifiedProofBundleError(
                "proof reuse must be NOT_REQUIRED when proof head equals merged main"
            )
        return {
            "decision": "NOT_REQUIRED",
            "source_head_sha": proof_head_sha,
            "current_head_sha": merged_main_sha,
            "all_artifact_blobs_identical": True,
            "all_dependency_blobs_identical": True,
        }

    if decision != "REUSE_APPROVED":
        raise UnifiedProofBundleError(
            "head movement requires REUSE_APPROVED proof reuse"
        )
    source_head = _bundle_sha(
        value.get("source_head_sha"),
        "proof_reuse.source_head_sha",
    )
    current_head = _bundle_sha(
        value.get("current_head_sha"),
        "proof_reuse.current_head_sha",
    )
    if source_head != proof_head_sha or current_head != merged_main_sha:
        raise UnifiedProofBundleError("proof_reuse head identity mismatch")
    if value.get("all_artifact_blobs_identical") is not True:
        raise UnifiedProofBundleError("proof reuse requires identical artifact blobs")
    if value.get("all_dependency_blobs_identical") is not True:
        raise UnifiedProofBundleError("proof reuse requires identical dependency blobs")
    return {
        "decision": "REUSE_APPROVED",
        "source_head_sha": source_head,
        "current_head_sha": current_head,
        "content_fingerprint": _bundle_hash64(
            value.get("content_fingerprint"),
            "proof_reuse.content_fingerprint",
            prefixed=False,
        ),
        "all_artifact_blobs_identical": True,
        "all_dependency_blobs_identical": True,
    }


def build_unified_proof_bundle(
    *,
    repository: str,
    checkpoint_id: str,
    workstream_id: str,
    proof_head_sha: str,
    merged_main_sha: str,
    focused_proof: Mapping[str, Any],
    devsystem_proof: Mapping[str, Any],
    terminal_receipt: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    dependencies: Mapping[str, Any],
    deployment: Mapping[str, Any],
    lineage: Mapping[str, Any],
    regression_debt: Mapping[str, Any],
    freeze_receipt: Mapping[str, Any],
    proof_reuse: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one deterministic, self-validating MONSTER certification packet."""
    repo = _bundle_text(repository, "repository").lower()
    if "/" not in repo:
        raise UnifiedProofBundleError("repository must be owner/name")
    checkpoint = _bundle_text(checkpoint_id, "checkpoint_id")
    workstream = _bundle_text(workstream_id, "workstream_id")
    proof_head = _bundle_sha(proof_head_sha, "proof_head_sha")
    merged_main = _bundle_sha(merged_main_sha, "merged_main_sha")

    focused = _bundle_run(
        focused_proof,
        field="focused_proof",
        proof_head_sha=proof_head,
        require_test_count=True,
        require_final_gate=False,
    )
    devsystem = _bundle_run(
        devsystem_proof,
        field="devsystem_proof",
        proof_head_sha=proof_head,
        require_test_count=False,
        require_final_gate=True,
    )
    receipt = _bundle_terminal_receipt(
        terminal_receipt,
        proof_head_sha=proof_head,
        devsystem_run_id=devsystem["run_id"],
    )
    artifact_map = _bundle_blob_map(
        artifacts,
        "artifacts",
        require_nonempty=True,
    )
    dependency_map = _bundle_blob_map(
        dependencies,
        "dependencies",
        require_nonempty=False,
    )
    overlap = sorted(set(artifact_map) & set(dependency_map))
    if overlap:
        raise UnifiedProofBundleError(
            "artifact/dependency paths must not overlap: " + ", ".join(overlap)
        )

    core = {
        "schema_version": 1,
        "version": UNIFIED_PROOF_BUNDLE_VERSION,
        "repository": repo,
        "checkpoint_id": checkpoint,
        "workstream_id": workstream,
        "proof_head_sha": proof_head,
        "merged_main_sha": merged_main,
        "focused_proof": focused,
        "devsystem_proof": devsystem,
        "terminal_receipt": receipt,
        "artifacts": artifact_map,
        "dependencies": dependency_map,
        "deployment": _bundle_deployment(
            deployment,
            merged_main_sha=merged_main,
        ),
        "lineage": _bundle_lineage(
            lineage,
            checkpoint_id=checkpoint,
        ),
        "regression_debt": _bundle_regression_debt(regression_debt),
        "freeze_receipt": _bundle_freeze_receipt(
            freeze_receipt,
            checkpoint_id=checkpoint,
            merged_main_sha=merged_main,
        ),
        "proof_reuse": _bundle_proof_reuse(
            proof_reuse,
            proof_head_sha=proof_head,
            merged_main_sha=merged_main,
        ),
        "certification_state": "CERTIFIED",
        "complete": True,
        "network_calls": False,
        "auto_fix": False,
        "may_modify_runtime": False,
        "mutation_authority": False,
    }
    bundle = dict(core)
    bundle["bundle_digest"] = "sha256:" + _bundle_sha256(core)
    return bundle


def validate_unified_proof_bundle(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate all proof identities and return the normalized bundle."""
    if not isinstance(value, Mapping):
        raise UnifiedProofBundleError("unified proof bundle must be an object")
    supplied = dict(value)
    if supplied.get("schema_version") != 1:
        raise UnifiedProofBundleError("unified proof bundle schema mismatch")
    if supplied.get("version") != UNIFIED_PROOF_BUNDLE_VERSION:
        raise UnifiedProofBundleError("unified proof bundle version mismatch")

    rebuilt = build_unified_proof_bundle(
        repository=supplied.get("repository"),
        checkpoint_id=supplied.get("checkpoint_id"),
        workstream_id=supplied.get("workstream_id"),
        proof_head_sha=supplied.get("proof_head_sha"),
        merged_main_sha=supplied.get("merged_main_sha"),
        focused_proof=supplied.get("focused_proof") or {},
        devsystem_proof=supplied.get("devsystem_proof") or {},
        terminal_receipt=supplied.get("terminal_receipt") or {},
        artifacts=supplied.get("artifacts") or {},
        dependencies=supplied.get("dependencies") or {},
        deployment=supplied.get("deployment") or {},
        lineage=supplied.get("lineage") or {},
        regression_debt=supplied.get("regression_debt") or {},
        freeze_receipt=supplied.get("freeze_receipt") or {},
        proof_reuse=supplied.get("proof_reuse") or {},
    )
    if supplied != rebuilt:
        raise UnifiedProofBundleError(
            "unified proof bundle is non-canonical or has been tampered with"
        )
    return rebuilt


def unified_proof_bundle_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a small control-room summary from a validated certification bundle."""
    bundle = validate_unified_proof_bundle(value)
    return {
        "version": bundle["version"],
        "checkpoint_id": bundle["checkpoint_id"],
        "certification_state": bundle["certification_state"],
        "proof_head_sha": bundle["proof_head_sha"],
        "merged_main_sha": bundle["merged_main_sha"],
        "focused_test_count": bundle["focused_proof"]["test_count"],
        "devsystem_run_id": bundle["devsystem_proof"]["run_id"],
        "terminal_receipt_hash": bundle["terminal_receipt"]["receipt_hash"],
        "artifact_count": len(bundle["artifacts"]),
        "dependency_count": len(bundle["dependencies"]),
        "deployment_status": bundle["deployment"]["status"],
        "regression_debt_state": bundle["regression_debt"]["state"],
        "freeze_status": bundle["freeze_receipt"]["status"],
        "bundle_digest": bundle["bundle_digest"],
        "complete": bundle["complete"],
        "mutation_authority": bundle["mutation_authority"],
    }


__all__ += [
    "UNIFIED_PROOF_BUNDLE_VERSION",
    "UnifiedProofBundleError",
    "build_unified_proof_bundle",
    "validate_unified_proof_bundle",
    "unified_proof_bundle_summary",
]


# ---------------------------------------------------------------------------
# MONSTER V8 Step 4 — compatibility contract for the established proof packet
# ---------------------------------------------------------------------------

PROOF_BUNDLE_NETWORK_CALLS = False
PROOF_BUNDLE_AUTO_MUTATE = False
PROOF_BUNDLE_MAY_MODIFY_RUNTIME = False
PROOF_BUNDLE_MUTATION_AUTHORITY = False

_build_unified_proof_bundle_strict = build_unified_proof_bundle
_validate_unified_proof_bundle_strict = validate_unified_proof_bundle


def _legacy_sha40(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text if _BUNDLE_SHA40.fullmatch(text) else None


def _legacy_digest(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    raw = text[7:] if text.startswith("sha256:") else text
    return f"sha256:{raw}" if _BUNDLE_HASH64.fullmatch(raw) else None


def _legacy_blob_map(value: Any) -> dict[str, str] | None:
    if not isinstance(value, Mapping) or not value:
        return None
    out: dict[str, str] = {}
    for raw_path, raw_sha in value.items():
        try:
            path = _bundle_path(raw_path)
        except UnifiedProofBundleError:
            return None
        sha = _legacy_sha40(raw_sha)
        if sha is None:
            return None
        out[path] = sha
    return dict(sorted(out.items()))


def _legacy_lane(
    value: Any,
    *,
    label: str,
    expected_head_sha: str,
    blockers: list[str],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        blockers.append(f"{label}:MISSING")
        return {}
    try:
        run_id = int(value.get("run_id"))
    except (TypeError, ValueError):
        run_id = 0
    status = str(value.get("status") or "").strip().upper()
    head_sha = str(value.get("head_sha") or "").strip().lower()
    try:
        test_count = int(value.get("test_count"))
    except (TypeError, ValueError):
        test_count = 0

    if run_id <= 0:
        blockers.append(f"{label}:RUN_ID_INVALID")
    if status != "SUCCESS":
        blockers.append(f"{label}:NOT_SUCCESS")
    if head_sha != expected_head_sha:
        blockers.append(f"{label}:HEAD_MISMATCH")
    if test_count <= 0:
        blockers.append(f"{label}:TEST_COUNT_INVALID")

    return {
        "run_id": run_id,
        "status": status,
        "head_sha": head_sha,
        "test_count": test_count,
    }


def _legacy_next_action(blockers: list[str]) -> str:
    if not blockers:
        return "CERTIFICATION_BUNDLE_GREEN"
    if "EXACT_HEAD_MISMATCH" in blockers:
        return "REFRESH_HEAD_AND_REBUILD_PROOF_BUNDLE"
    if any(
        item.startswith("FOCUSED_PROOF:")
        or item.startswith("DEVSYSTEM_PROOF:")
        for item in blockers
    ):
        return "RESOLVE_EXACT_HEAD_PROOF_FAILURE"
    if "TERMINAL_RECEIPT_DIGEST_INVALID" in blockers:
        return "RESOLVE_TERMINAL_RECEIPT"
    if "REGRESSION_DEBT_NOT_CLEARED" in blockers:
        return "CLEAR_REGRESSION_DEBT"
    if any(item.startswith("FREEZE_") for item in blockers):
        return "REGISTER_OR_REPAIR_FROZEN_CHECKPOINT"
    if any(item.startswith("DEPLOYMENT_") for item in blockers):
        return "RESTORE_DEPLOYMENT_CERTIFICATION"
    if any(item.startswith("LINEAGE_") for item in blockers):
        return "REBUILD_CAUSAL_LINEAGE_EVIDENCE"
    if (
        "ARTIFACT_IDENTITY_MISSING_OR_INVALID" in blockers
        or "DEPENDENCY_IDENTITY_MISSING_OR_INVALID" in blockers
    ):
        return "REBUILD_CONTENT_IDENTITY_MANIFEST"
    return "RUN_AUTOMATIC_ROOT_CAUSE_BACKTRACE"


def _build_unified_proof_bundle_legacy(
    *,
    checkpoint_id: str,
    repository: str,
    expected_head_sha: str,
    observed_head_sha: str,
    focused_proof: Mapping[str, Any],
    devsystem_proof: Mapping[str, Any],
    terminal_receipt_digest: str,
    artifacts: Mapping[str, Any],
    dependencies: Mapping[str, Any],
    regression_debt_state: str,
    require_freeze: bool = False,
    freeze_record: Mapping[str, Any] | None = None,
    require_deployment: bool = False,
    deployment_evidence: Mapping[str, Any] | None = None,
    lineage_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    checkpoint = str(checkpoint_id or "").strip()
    repo = str(repository or "").strip().lower()
    expected = str(expected_head_sha or "").strip().lower()
    observed = str(observed_head_sha or "").strip().lower()
    blockers: list[str] = []

    if not checkpoint:
        blockers.append("CHECKPOINT_ID_MISSING")
    if "/" not in repo:
        blockers.append("REPOSITORY_INVALID")
    if _legacy_sha40(expected) is None:
        blockers.append("EXPECTED_HEAD_INVALID")
    if _legacy_sha40(observed) is None:
        blockers.append("OBSERVED_HEAD_INVALID")

    exact_head = bool(
        _legacy_sha40(expected)
        and _legacy_sha40(observed)
        and expected == observed
    )
    if not exact_head:
        blockers.append("EXACT_HEAD_MISMATCH")

    focused = _legacy_lane(
        focused_proof,
        label="FOCUSED_PROOF",
        expected_head_sha=expected,
        blockers=blockers,
    )
    devsystem = _legacy_lane(
        devsystem_proof,
        label="DEVSYSTEM_PROOF",
        expected_head_sha=expected,
        blockers=blockers,
    )

    receipt = _legacy_digest(terminal_receipt_digest)
    if receipt is None:
        blockers.append("TERMINAL_RECEIPT_DIGEST_INVALID")

    artifact_map = _legacy_blob_map(artifacts)
    if artifact_map is None:
        blockers.append("ARTIFACT_IDENTITY_MISSING_OR_INVALID")
        artifact_map = {}

    dependency_map = _legacy_blob_map(dependencies)
    if dependency_map is None:
        blockers.append("DEPENDENCY_IDENTITY_MISSING_OR_INVALID")
        dependency_map = {}

    debt = str(regression_debt_state or "").strip().upper()
    if debt != "CLEARED":
        blockers.append("REGRESSION_DEBT_NOT_CLEARED")

    normalized_freeze: dict[str, Any] | None = None
    if require_freeze:
        if not isinstance(freeze_record, Mapping):
            blockers.append("FREEZE_RECORD_REQUIRED")
        else:
            freeze_status = str(freeze_record.get("status") or "").strip().upper()
            freeze_head = str(
                freeze_record.get("source_main_sha") or ""
            ).strip().lower()
            try:
                freeze_revision = int(freeze_record.get("registry_revision"))
            except (TypeError, ValueError):
                freeze_revision = 0
            freeze_hash = _legacy_digest(freeze_record.get("state_hash"))
            if freeze_status != "FROZEN":
                blockers.append("FREEZE_STATUS_NOT_FROZEN")
            if freeze_head != expected:
                blockers.append("FREEZE_HEAD_MISMATCH")
            if freeze_revision <= 0 or freeze_hash is None:
                blockers.append("FREEZE_RECORD_INVALID")
            normalized_freeze = {
                "status": freeze_status,
                "source_main_sha": freeze_head,
                "registry_revision": freeze_revision,
                "state_hash": freeze_hash,
            }

    normalized_deployment: dict[str, Any] | None = None
    if require_deployment:
        if not isinstance(deployment_evidence, Mapping):
            blockers.append("DEPLOYMENT_EVIDENCE_REQUIRED")
        else:
            dep_status = str(
                deployment_evidence.get("status") or ""
            ).strip().upper()
            dep_head = str(
                deployment_evidence.get("head_sha") or ""
            ).strip().lower()
            dep_certified = deployment_evidence.get("certified") is True
            if dep_status != "GREEN" or not dep_certified:
                blockers.append("DEPLOYMENT_NOT_GREEN")
            if dep_head != expected:
                blockers.append("DEPLOYMENT_HEAD_MISMATCH")
            normalized_deployment = {
                "status": dep_status,
                "head_sha": dep_head,
                "certified": dep_certified,
            }

    normalized_lineage: dict[str, Any] | None = None
    if lineage_evidence is not None:
        if not isinstance(lineage_evidence, Mapping):
            blockers.append("LINEAGE_EVIDENCE_INVALID")
        else:
            lineage_status = str(
                lineage_evidence.get("status") or ""
            ).strip().upper()
            lineage_head = str(
                lineage_evidence.get("head_sha") or ""
            ).strip().lower()
            lineage_digest = _legacy_digest(
                lineage_evidence.get("lineage_digest")
            )
            if lineage_status != "GREEN":
                blockers.append("LINEAGE_NOT_GREEN")
            if lineage_head != expected:
                blockers.append("LINEAGE_HEAD_MISMATCH")
            if lineage_digest is None:
                blockers.append("LINEAGE_DIGEST_INVALID")
            normalized_lineage = {
                "status": lineage_status,
                "head_sha": lineage_head,
                "lineage_digest": lineage_digest,
            }

    blockers = sorted(set(blockers))
    core = {
        "version": UNIFIED_PROOF_BUNDLE_VERSION,
        "checkpoint_id": checkpoint,
        "repository": repo,
        "expected_head_sha": expected,
        "observed_head_sha": observed,
        "exact_head": exact_head,
        "focused_proof": focused,
        "devsystem_proof": devsystem,
        "terminal_receipt_digest": receipt or str(
            terminal_receipt_digest or ""
        ).strip(),
        "artifacts": artifact_map,
        "dependencies": dependency_map,
        "regression_debt_state": debt,
        "require_freeze": bool(require_freeze),
        "freeze_record": normalized_freeze,
        "require_deployment": bool(require_deployment),
        "deployment_evidence": normalized_deployment,
        "lineage_evidence": normalized_lineage,
        "status": "GREEN" if not blockers else "BLOCKED",
        "blockers": blockers,
        "next_legal_action": _legacy_next_action(blockers),
        "step_2a_required": True,
        "network_calls": PROOF_BUNDLE_NETWORK_CALLS,
        "auto_mutate": PROOF_BUNDLE_AUTO_MUTATE,
        "may_modify_runtime": PROOF_BUNDLE_MAY_MODIFY_RUNTIME,
        "mutation_authority": PROOF_BUNDLE_MUTATION_AUTHORITY,
    }
    bundle = dict(core)
    bundle["bundle_digest"] = "sha256:" + _bundle_sha256(core)
    return bundle


def build_unified_proof_bundle(**kwargs: Any) -> dict[str, Any]:
    """Build either the established gate packet or the strict final packet."""
    if (
        "expected_head_sha" in kwargs
        or "observed_head_sha" in kwargs
        or "terminal_receipt_digest" in kwargs
    ):
        return _build_unified_proof_bundle_legacy(**kwargs)
    return _build_unified_proof_bundle_strict(**kwargs)


def validate_unified_proof_bundle(
    value: Mapping[str, Any],
    *,
    require_green: bool = False,
) -> dict[str, Any]:
    """Validate either unified bundle representation without weakening either."""
    if not isinstance(value, Mapping):
        raise UnifiedProofBundleError("unified proof bundle must be an object")

    if value.get("schema_version") == 1:
        bundle = _validate_unified_proof_bundle_strict(value)
        if require_green and bundle.get("certification_state") != "CERTIFIED":
            raise UnifiedProofBundleError(
                "unified proof bundle is not certified green"
            )
        return bundle

    supplied = dict(value)
    digest = supplied.get("bundle_digest")
    core = dict(supplied)
    core.pop("bundle_digest", None)
    expected = "sha256:" + _bundle_sha256(core)
    if digest != expected:
        raise UnifiedProofBundleError("unified proof bundle digest mismatch")
    if supplied.get("version") != UNIFIED_PROOF_BUNDLE_VERSION:
        raise UnifiedProofBundleError("unified proof bundle version mismatch")
    if supplied.get("mutation_authority") is not False:
        raise UnifiedProofBundleError(
            "unified proof bundle cannot grant mutation authority"
        )
    if supplied.get("step_2a_required") is not True:
        raise UnifiedProofBundleError(
            "unified proof bundle must require Step 2A"
        )
    if require_green and supplied.get("status") != "GREEN":
        raise UnifiedProofBundleError(
            "unified proof bundle is not GREEN"
        )
    return supplied


__all__ += [
    "PROOF_BUNDLE_NETWORK_CALLS",
    "PROOF_BUNDLE_AUTO_MUTATE",
    "PROOF_BUNDLE_MAY_MODIFY_RUNTIME",
    "PROOF_BUNDLE_MUTATION_AUTHORITY",
]
