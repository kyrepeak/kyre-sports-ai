"""Step 6G status graduation for the certified MLB 25% production cohort.

This layer changes rollout status only. It reuses the existing Step 6D exposure,
cohort selection, rollback controls, and downstream model behavior unchanged.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

DATA_TYPE = "mlb_step6g_controlled_graduation_v1"
SCHEMA_VERSION = 1
GRADUATED_PRODUCTION_PERCENT = 25.0
MAX_GRADUATED_PRODUCTION_PERCENT = 25.0
STEP6F_CERTIFIED_MAIN_SHA = "14ac9d0ed9cb646743b754470b214c5423a30664"
STEP6F_CERTIFICATION_RUN_ID = 33420081102
STEP6F_CERTIFICATION_MARKER = "MLB_STEP6F_PRODUCTION_GRADUATION_GATE_GREEN"

CERTIFIED_STEP6F_DECISION: dict[str, Any] = {
    "data_type": "mlb_step6f_production_graduation_gate_v1",
    "schema_version": 1,
    "decision": "GRADUATION_ALLOWED",
    "graduation_eligible": True,
    "current_production_percent": 25.0,
    "permitted_graduated_percent": 25.0,
    "exposure_increase_authorized": False,
    "automatic_runtime_mutation": False,
    "requires_separate_activation_step": True,
    "failures": [],
}


class MLBStep6GControlledGraduationError(ValueError):
    pass


def _float(value: object, *, label: str) -> float:
    if isinstance(value, bool):
        raise MLBStep6GControlledGraduationError(f"{label} must be numeric")
    try:
        parsed = float(value)
    except Exception as exc:
        raise MLBStep6GControlledGraduationError(f"{label} must be numeric") from exc
    if not math.isfinite(parsed):
        raise MLBStep6GControlledGraduationError(f"{label} must be finite")
    return parsed


def validate_step6f_permission(permission: Mapping[str, Any] | None) -> tuple[bool, list[str]]:
    if permission is not None and not isinstance(permission, Mapping):
        raise MLBStep6GControlledGraduationError("permission must be a mapping")
    report = dict(permission or {})
    failures: list[str] = []
    if report.get("data_type") != "mlb_step6f_production_graduation_gate_v1":
        failures.append("STEP6F_DATA_TYPE_MISMATCH")
    if report.get("schema_version") != 1:
        failures.append("STEP6F_SCHEMA_VERSION_MISMATCH")
    if report.get("decision") != "GRADUATION_ALLOWED":
        failures.append("STEP6F_DECISION_NOT_ALLOWED")
    if report.get("graduation_eligible") is not True:
        failures.append("STEP6F_GRADUATION_NOT_ELIGIBLE")
    for field in ("current_production_percent", "permitted_graduated_percent"):
        try:
            value = _float(report.get(field, math.nan), label=field)
        except MLBStep6GControlledGraduationError:
            value = math.nan
            failures.append(f"STEP6F_{field.upper()}_INVALID")
        if not math.isfinite(value) or abs(value - 25.0) > 1e-12:
            failures.append(f"STEP6F_{field.upper()}_NOT_25")
    if report.get("exposure_increase_authorized") is not False:
        failures.append("STEP6F_EXPOSURE_INCREASE_CONTRACT_DRIFT")
    if report.get("automatic_runtime_mutation") is not False:
        failures.append("STEP6F_RUNTIME_MUTATION_CONTRACT_DRIFT")
    if report.get("requires_separate_activation_step") is not True:
        failures.append("STEP6F_SEPARATE_ACTIVATION_CONTRACT_DRIFT")
    if list(report.get("failures") or []):
        failures.append("STEP6F_FAILURES_PRESENT")
    return (not failures), list(dict.fromkeys(failures))


def resolve_step6g_controlled_graduation(
    step6d_config: Mapping[str, Any],
    *,
    permission: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(step6d_config, Mapping):
        raise MLBStep6GControlledGraduationError("step6d_config must be a mapping")
    rollout = dict(step6d_config)
    permission_map = CERTIFIED_STEP6F_DECISION if permission is None else permission
    permission_valid, permission_failures = validate_step6f_permission(permission_map)

    failures = list(permission_failures)
    if rollout.get("data_type") != "mlb_step6d_production_expansion_v1":
        failures.append("STEP6D_DATA_TYPE_MISMATCH")
    if rollout.get("schema_version") != 1:
        failures.append("STEP6D_SCHEMA_VERSION_MISMATCH")
    if rollout.get("exact_rollback") is not True:
        failures.append("STEP6D_EXACT_ROLLBACK_CONTRACT_DRIFT")
    if rollout.get("config_valid") is not True:
        failures.append("STEP6D_CONFIG_NOT_VALID")

    try:
        effective = _float(rollout.get("effective_percent", 0.0), label="effective_percent")
    except MLBStep6GControlledGraduationError:
        effective = 0.0
        failures.append("STEP6D_EFFECTIVE_PERCENT_INVALID")
    if effective > MAX_GRADUATED_PRODUCTION_PERCENT + 1e-12:
        failures.append("STEP6D_EFFECTIVE_PERCENT_EXCEEDS_25")

    enabled = rollout.get("enabled") is True and effective > 0.0
    rollback = str(rollout.get("control_source") or "") in {
        "GLOBAL_KILL_SWITCH",
        "STREAMLIT_SESSION_ROLLBACK",
    }
    graduated = bool(
        permission_valid
        and not failures
        and enabled
        and abs(effective - GRADUATED_PRODUCTION_PERCENT) <= 1e-12
    )
    if rollback or not enabled:
        status = "GRADUATED_PRODUCTION_ROLLBACK"
    elif graduated:
        status = "GRADUATED_PRODUCTION_ACTIVE"
    else:
        status = "CANARY_HOLD_AT_25_PERCENT"

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "graduation_status": status,
        "graduated_production_active": graduated,
        "canary_status_retired": graduated,
        "step6f_permission_valid": permission_valid,
        "step6f_permission_failures": permission_failures,
        "step6f_certified_main_sha": STEP6F_CERTIFIED_MAIN_SHA,
        "step6f_certification_run_id": STEP6F_CERTIFICATION_RUN_ID,
        "step6f_certification_marker": STEP6F_CERTIFICATION_MARKER,
        "step6d_control_source": rollout.get("control_source"),
        "step6d_enabled": bool(rollout.get("enabled")),
        "step6d_effective_percent": effective,
        "graduated_production_percent": GRADUATED_PRODUCTION_PERCENT,
        "max_graduated_production_percent": MAX_GRADUATED_PRODUCTION_PERCENT,
        "production_exposure_changed": False,
        "exposure_change_percent": 0.0,
        "exposure_increase_authorized": False,
        "step6d_rollout_reused": True,
        "exact_rollback_preserved": rollout.get("exact_rollback") is True,
        "failures": list(dict.fromkeys(failures)),
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "GRADUATED_PRODUCTION_PERCENT",
    "MAX_GRADUATED_PRODUCTION_PERCENT",
    "STEP6F_CERTIFIED_MAIN_SHA",
    "STEP6F_CERTIFICATION_RUN_ID",
    "STEP6F_CERTIFICATION_MARKER",
    "CERTIFIED_STEP6F_DECISION",
    "MLBStep6GControlledGraduationError",
    "validate_step6f_permission",
    "resolve_step6g_controlled_graduation",
]
