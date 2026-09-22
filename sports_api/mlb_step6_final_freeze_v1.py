"""MLB Step 6H final production freeze attestation.

Step 6H is deliberately non-behavioral. It records the certified Step 6A-6G
production chain and provides a pure validation boundary for the final MLB
full-game 25% graduated-production state. It does not mutate rollout state,
change model math, alter selection/risk behavior, persist data, place wagers,
price-gate player props, or affect WNBA behavior.
"""
from __future__ import annotations

from typing import Any, Mapping

DATA_TYPE = "mlb_step6_final_freeze_v1"
SCHEMA_VERSION = 1
STEP6H_BASE_MAIN_SHA = "b094a38c1bf47f7222dbf2d21216e419ab218084"
FINAL_PRODUCTION_PERCENT = 25.0
MAX_PRODUCTION_PERCENT = 25.0
FINAL_GRADUATION_STATUS = "GRADUATED_PRODUCTION_ACTIVE"
FINAL_FREEZE_STATUS = "STEP6_FROZEN_GRADUATED_PRODUCTION"
FINAL_CERTIFICATION_MARKER = "MLB_STEP6H_FINAL_PRODUCTION_FREEZE_GREEN"

STEP6_STAGE_CHAIN = (
    "6A_PRODUCTION_CANARY_ACTIVATION",
    "6B_PRODUCTION_CANARY_MONITORING",
    "6C_EVIDENCE_GATED_EXPANSION",
    "6D_CONTROLLED_25_PERCENT_ACTIVATION",
    "6E_25_PERCENT_STABILITY_WINDOW",
    "6F_PRODUCTION_GRADUATION_GATE",
    "6G_CONTROLLED_PRODUCTION_GRADUATION",
)

STEP6_CERTIFICATION_MARKERS = (
    "MLB_STEP6A_PRODUCTION_CANARY_GREEN",
    "MLB_STEP6B_MULTI_CYCLE_MONITOR_GREEN",
    "MLB_STEP6C_EVIDENCE_GATED_EXPANSION_GREEN",
    "MLB_STEP6D_CONTROLLED_25_PRODUCTION_GREEN",
    "MLB_STEP6E_25PCT_PRODUCTION_STABILITY_GREEN",
    "MLB_STEP6F_PRODUCTION_GRADUATION_GATE_GREEN",
    "MLB_STEP6G_CONTROLLED_PRODUCTION_GRADUATION_GREEN",
)

PROTECTED_INVARIANTS = {
    "model_math_impact": False,
    "pick_strength_impact": False,
    "ranking_math_impact": False,
    "risk_logic_impact": False,
    "wagering_impact": False,
    "durable_persistence": False,
    "player_props_price_gated": False,
    "wnba_impact": False,
}


class MLBStep6FinalFreezeError(ValueError):
    pass


def _mapping(value: Mapping[str, Any] | None, *, label: str) -> dict[str, Any]:
    if value is None or not isinstance(value, Mapping):
        raise MLBStep6FinalFreezeError(f"{label} must be a mapping")
    return dict(value)


def validate_final_step6_runtime(
    step6d_config: Mapping[str, Any] | None,
    step6g_status: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate the frozen final Step 6 state without mutating runtime state."""
    rollout = _mapping(step6d_config, label="step6d_config")
    graduation = _mapping(step6g_status, label="step6g_status")
    failures: list[str] = []

    if rollout.get("data_type") != "mlb_step6d_production_expansion_v1":
        failures.append("STEP6D_DATA_TYPE_MISMATCH")
    if rollout.get("schema_version") != 1:
        failures.append("STEP6D_SCHEMA_VERSION_MISMATCH")
    if rollout.get("enabled") is not True:
        failures.append("STEP6D_NOT_ENABLED")
    if rollout.get("config_valid") is not True:
        failures.append("STEP6D_CONFIG_NOT_VALID")
    if rollout.get("exact_rollback") is not True:
        failures.append("STEP6D_EXACT_ROLLBACK_NOT_PRESERVED")
    if rollout.get("step6c_permission_valid") is not True:
        failures.append("STEP6C_PERMISSION_NOT_VALID")
    try:
        rollout_percent = float(rollout.get("effective_percent"))
    except Exception:
        rollout_percent = -1.0
        failures.append("STEP6D_PERCENT_INVALID")
    if abs(rollout_percent - FINAL_PRODUCTION_PERCENT) > 1e-12:
        failures.append("STEP6D_PERCENT_NOT_25")
    if rollout_percent > MAX_PRODUCTION_PERCENT + 1e-12:
        failures.append("STEP6D_PERCENT_EXCEEDS_FINAL_CAP")

    if graduation.get("data_type") != "mlb_step6g_controlled_graduation_v1":
        failures.append("STEP6G_DATA_TYPE_MISMATCH")
    if graduation.get("schema_version") != 1:
        failures.append("STEP6G_SCHEMA_VERSION_MISMATCH")
    if graduation.get("graduation_status") != FINAL_GRADUATION_STATUS:
        failures.append("STEP6G_NOT_GRADUATED_ACTIVE")
    if graduation.get("graduated_production_active") is not True:
        failures.append("STEP6G_GRADUATED_FLAG_NOT_ACTIVE")
    if graduation.get("canary_status_retired") is not True:
        failures.append("STEP6G_CANARY_STATUS_NOT_RETIRED")
    if graduation.get("step6f_permission_valid") is not True:
        failures.append("STEP6F_PERMISSION_NOT_VALID")
    if graduation.get("step6d_rollout_reused") is not True:
        failures.append("STEP6D_ROLLOUT_NOT_REUSED")
    if graduation.get("exact_rollback_preserved") is not True:
        failures.append("STEP6G_EXACT_ROLLBACK_NOT_PRESERVED")
    if graduation.get("production_exposure_changed") is not False:
        failures.append("STEP6G_EXPOSURE_CHANGED")
    if graduation.get("exposure_increase_authorized") is not False:
        failures.append("STEP6G_EXPOSURE_INCREASE_AUTHORIZED")
    try:
        graduated_percent = float(graduation.get("graduated_production_percent"))
        exposure_change = float(graduation.get("exposure_change_percent"))
    except Exception:
        graduated_percent = -1.0
        exposure_change = 1.0
        failures.append("STEP6G_PERCENT_FIELDS_INVALID")
    if abs(graduated_percent - FINAL_PRODUCTION_PERCENT) > 1e-12:
        failures.append("STEP6G_PERCENT_NOT_25")
    if abs(exposure_change) > 1e-12:
        failures.append("STEP6G_EXPOSURE_CHANGE_NOT_ZERO")
    if list(graduation.get("failures") or []):
        failures.append("STEP6G_FAILURES_PRESENT")

    failures = list(dict.fromkeys(failures))
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "freeze_status": FINAL_FREEZE_STATUS if not failures else "STEP6_FREEZE_REJECTED",
        "freeze_eligible": not failures,
        "step6h_base_main_sha": STEP6H_BASE_MAIN_SHA,
        "final_production_percent": FINAL_PRODUCTION_PERCENT,
        "max_production_percent": MAX_PRODUCTION_PERCENT,
        "final_graduation_status": FINAL_GRADUATION_STATUS,
        "stage_chain": list(STEP6_STAGE_CHAIN),
        "certification_markers": list(STEP6_CERTIFICATION_MARKERS),
        "failures": failures,
        "read_only_freeze": True,
        "automatic_runtime_mutation": False,
        "production_exposure_changed": False,
        "exact_rollback_required": True,
        **PROTECTED_INVARIANTS,
    }


def final_freeze_manifest() -> dict[str, Any]:
    """Return the immutable Step 6 freeze contract."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step6h_base_main_sha": STEP6H_BASE_MAIN_SHA,
        "final_production_percent": FINAL_PRODUCTION_PERCENT,
        "max_production_percent": MAX_PRODUCTION_PERCENT,
        "final_graduation_status": FINAL_GRADUATION_STATUS,
        "final_freeze_status": FINAL_FREEZE_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "stage_chain": list(STEP6_STAGE_CHAIN),
        "certification_markers": list(STEP6_CERTIFICATION_MARKERS),
        "read_only_freeze": True,
        "automatic_runtime_mutation": False,
        "production_exposure_changed": False,
        "exact_rollback_required": True,
        **PROTECTED_INVARIANTS,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP6H_BASE_MAIN_SHA",
    "FINAL_PRODUCTION_PERCENT",
    "MAX_PRODUCTION_PERCENT",
    "FINAL_GRADUATION_STATUS",
    "FINAL_FREEZE_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "STEP6_STAGE_CHAIN",
    "STEP6_CERTIFICATION_MARKERS",
    "PROTECTED_INVARIANTS",
    "MLBStep6FinalFreezeError",
    "validate_final_step6_runtime",
    "final_freeze_manifest",
]
