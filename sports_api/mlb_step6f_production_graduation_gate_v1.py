"""MLB Step 6F production graduation gate.

Consumes Step 6E's longer 25% production stability evidence and decides whether
the already-active 25% MLB full-game price-gate cohort is eligible to graduate
from canary status. Step 6F is a read-only decision boundary: it does not expand
exposure, mutate runtime state, place wagers, persist data, price-gate player
props, or affect WNBA behavior.

A GREEN Step 6F result only authorizes a separate graduation activation step.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

DATA_TYPE = "mlb_step6f_production_graduation_gate_v1"
SCHEMA_VERSION = 1
CURRENT_PRODUCTION_PERCENT = 25.0
MAX_GRADUATED_PERCENT = 25.0
REQUIRED_STEP6E_DATA_TYPE = "mlb_step6e_25pct_stability_window_v1"
REQUIRED_STEP6E_SCHEMA_VERSION = 1
MIN_REQUIRED_CYCLES = 12
MIN_REQUIRED_DISTINCT_SNAPSHOTS = 8
MAX_ALLOWED_FEED_AGE_SECONDS = 60.0

STEP6E_CERTIFIED_MAIN_SHA = "f4a9113d7cf3a5b9f3a9bd7a266ff939d7f24887"
STEP6E_CERTIFICATION_RUN_ID = 33418711228
STEP6E_CERTIFICATION_MARKER = "MLB_STEP6E_25PCT_PRODUCTION_STABILITY_GREEN"


class MLBStep6FGraduationGateError(ValueError):
    pass


def _as_int(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        raise MLBStep6FGraduationGateError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except Exception as exc:
        raise MLBStep6FGraduationGateError(f"{label} must be an integer") from exc
    return parsed


def _as_float(value: object, *, label: str) -> float:
    if isinstance(value, bool):
        raise MLBStep6FGraduationGateError(f"{label} must be numeric")
    try:
        parsed = float(value)
    except Exception as exc:
        raise MLBStep6FGraduationGateError(f"{label} must be numeric") from exc
    if not math.isfinite(parsed):
        raise MLBStep6FGraduationGateError(f"{label} must be finite")
    return parsed


def evaluate_production_graduation(stability_report: Mapping[str, Any] | None) -> dict[str, Any]:
    """Evaluate Step 6E evidence without mutating any production state."""
    if stability_report is not None and not isinstance(stability_report, Mapping):
        raise MLBStep6FGraduationGateError("stability_report must be a mapping")
    report = dict(stability_report or {})
    failures: list[str] = []

    if report.get("data_type") != REQUIRED_STEP6E_DATA_TYPE:
        failures.append("STEP6E_DATA_TYPE_MISMATCH")
    if report.get("schema_version") != REQUIRED_STEP6E_SCHEMA_VERSION:
        failures.append("STEP6E_SCHEMA_VERSION_MISMATCH")
    if report.get("stability_result") != "GREEN":
        failures.append("STEP6E_STABILITY_NOT_GREEN")
    if report.get("graduation_evidence_ready") is not True:
        failures.append("STEP6E_GRADUATION_EVIDENCE_NOT_READY")

    try:
        cycle_count = _as_int(report.get("cycle_count", -1), label="cycle_count")
    except MLBStep6FGraduationGateError:
        cycle_count = -1
        failures.append("STEP6E_CYCLE_COUNT_INVALID")
    if cycle_count < MIN_REQUIRED_CYCLES:
        failures.append("STEP6E_INSUFFICIENT_CYCLES")

    try:
        distinct_snapshots = _as_int(report.get("distinct_snapshot_count", -1), label="distinct_snapshot_count")
    except MLBStep6FGraduationGateError:
        distinct_snapshots = -1
        failures.append("STEP6E_DISTINCT_SNAPSHOT_COUNT_INVALID")
    if distinct_snapshots < MIN_REQUIRED_DISTINCT_SNAPSHOTS:
        failures.append("STEP6E_INSUFFICIENT_DISTINCT_SNAPSHOTS")

    try:
        feed_age = _as_float(report.get("max_feed_age_seconds", math.inf), label="max_feed_age_seconds")
    except MLBStep6FGraduationGateError:
        feed_age = math.inf
        failures.append("STEP6E_FEED_AGE_INVALID")
    if feed_age > MAX_ALLOWED_FEED_AGE_SECONDS:
        failures.append("STEP6E_FEED_TOO_OLD")

    try:
        stale_cycles = _as_int(report.get("stale_cycle_count", -1), label="stale_cycle_count")
    except MLBStep6FGraduationGateError:
        stale_cycles = -1
        failures.append("STEP6E_STALE_CYCLE_COUNT_INVALID")
    if stale_cycles != 0:
        failures.append("STEP6E_STALE_CYCLES_PRESENT")

    if report.get("same_slate_cohort_deterministic") is not True:
        failures.append("STEP6E_COHORT_NOT_DETERMINISTIC")
    if list(report.get("violations") or []):
        failures.append("STEP6E_VIOLATIONS_PRESENT")
    if list(report.get("warnings") or []):
        failures.append("STEP6E_WARNINGS_PRESENT")

    try:
        target_percent = _as_float(report.get("target_production_percent", math.nan), label="target_production_percent")
    except MLBStep6FGraduationGateError:
        target_percent = math.nan
        failures.append("STEP6E_TARGET_PERCENT_INVALID")
    if not math.isfinite(target_percent) or abs(target_percent - CURRENT_PRODUCTION_PERCENT) > 1e-12:
        failures.append("STEP6E_TARGET_PERCENT_NOT_25")

    try:
        max_percent = _as_float(report.get("max_production_percent", math.nan), label="max_production_percent")
    except MLBStep6FGraduationGateError:
        max_percent = math.nan
        failures.append("STEP6E_MAX_PERCENT_INVALID")
    if not math.isfinite(max_percent) or abs(max_percent - MAX_GRADUATED_PERCENT) > 1e-12:
        failures.append("STEP6E_MAX_PERCENT_NOT_25")

    def count(name: str) -> int:
        try:
            return _as_int(report.get(name, -1), label=name)
        except MLBStep6FGraduationGateError:
            failures.append(f"STEP6E_{name.upper()}_INVALID")
            return -1

    total_checks = count("total_checks")
    total_enrolled = count("total_enrolled_checks")
    total_allow = count("total_allow_count")
    total_block = count("total_block_count")
    total_non = count("total_nonenrolled_passthrough")
    total_rollback = count("total_rollback_passthrough")
    total_line_bearing = count("total_line_bearing_checks")

    if total_checks <= 0:
        failures.append("STEP6E_NO_LIVE_CHECKS")
    if total_enrolled <= 0:
        failures.append("STEP6E_NO_ENROLLED_CHECKS")
    if total_allow + total_block != total_enrolled:
        failures.append("STEP6E_GATE_PARTITION_MISMATCH")
    if total_non + total_enrolled != total_checks:
        failures.append("STEP6E_PRODUCTION_PARTITION_MISMATCH")
    if total_rollback != total_checks:
        failures.append("STEP6E_ROLLBACK_NOT_EXACT")
    if total_line_bearing <= 0:
        failures.append("STEP6E_NO_LINE_BEARING_CHECKS")

    if report.get("read_only_monitor") is not True:
        failures.append("STEP6E_MONITOR_NOT_READ_ONLY")
    if report.get("automatic_runtime_mutation") is not False:
        failures.append("STEP6E_RUNTIME_MUTATION_CONTRACT_DRIFT")
    if report.get("requires_separate_graduation_step") is not True:
        failures.append("STEP6E_SEPARATE_GRADUATION_CONTRACT_DRIFT")
    if report.get("scheduled_monitor_safe") is not True:
        failures.append("STEP6E_SCHEDULED_MONITOR_NOT_SAFE")

    for field in (
        "model_math_impact",
        "pick_strength_impact",
        "ranking_math_impact",
        "risk_logic_impact",
        "wagering_impact",
        "durable_persistence",
        "player_props_price_gated",
        "wnba_impact",
    ):
        if report.get(field) is not False:
            failures.append(f"STEP6E_PROTECTED_FLAG_DRIFT:{field}")

    failures = list(dict.fromkeys(failures))
    allowed = not failures
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "decision": "GRADUATION_ALLOWED" if allowed else "HOLD_AT_25_PERCENT",
        "graduation_eligible": allowed,
        "current_production_percent": CURRENT_PRODUCTION_PERCENT,
        "permitted_graduated_percent": MAX_GRADUATED_PERCENT if allowed else CURRENT_PRODUCTION_PERCENT,
        "exposure_increase_authorized": False,
        "automatic_runtime_mutation": False,
        "requires_separate_activation_step": True,
        "step6e_certified_main_sha": STEP6E_CERTIFIED_MAIN_SHA,
        "step6e_certification_run_id": STEP6E_CERTIFICATION_RUN_ID,
        "step6e_certification_marker": STEP6E_CERTIFICATION_MARKER,
        "observed_cycle_count": cycle_count,
        "observed_distinct_snapshot_count": distinct_snapshots,
        "observed_max_feed_age_seconds": feed_age,
        "observed_stale_cycle_count": stale_cycles,
        "observed_total_checks": total_checks,
        "observed_enrolled_checks": total_enrolled,
        "observed_allow_count": total_allow,
        "observed_block_count": total_block,
        "observed_rollback_passthrough": total_rollback,
        "failures": failures,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "player_props_price_gated": False,
        "wnba_impact": False,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "CURRENT_PRODUCTION_PERCENT",
    "MAX_GRADUATED_PERCENT",
    "REQUIRED_STEP6E_DATA_TYPE",
    "REQUIRED_STEP6E_SCHEMA_VERSION",
    "MIN_REQUIRED_CYCLES",
    "MIN_REQUIRED_DISTINCT_SNAPSHOTS",
    "MAX_ALLOWED_FEED_AGE_SECONDS",
    "STEP6E_CERTIFIED_MAIN_SHA",
    "STEP6E_CERTIFICATION_RUN_ID",
    "STEP6E_CERTIFICATION_MARKER",
    "MLBStep6FGraduationGateError",
    "evaluate_production_graduation",
]
