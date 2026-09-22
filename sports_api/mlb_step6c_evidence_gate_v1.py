"""MLB Step 6C evidence gate for expanding the Step 6A production canary.

This layer is intentionally policy-only. It consumes a Step 6B monitor-window
report and decides whether an operator/runtime is *permitted* to expand the MLB
full-game price gate above the currently active 10% canary, up to a hard 25%
ceiling. It never changes rollout state by itself.

Fail-closed behavior is deliberate: missing, malformed, stale, warning-bearing,
or RED evidence holds the system at the already-certified 10% exposure.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

DATA_TYPE = "mlb_step6c_evidence_gate_v1"
SCHEMA_VERSION = 1
CURRENT_CERTIFIED_PERCENT = 10.0
MAX_EXPANSION_PERCENT = 25.0
REQUIRED_MONITOR_DATA_TYPE = "mlb_step6b_canary_monitor_window_v1"
REQUIRED_MONITOR_SCHEMA_VERSION = 1
MIN_REQUIRED_CYCLES = 4
MIN_DISTINCT_SNAPSHOTS = 4
MAX_EXPANSION_FEED_AGE_SECONDS = 60.0


class MLBStep6CEvidenceGateError(ValueError):
    pass


def _finite_percent(value: object) -> float:
    if isinstance(value, bool):
        raise MLBStep6CEvidenceGateError("requested_percent must be numeric")
    try:
        parsed = float(value)
    except Exception as exc:
        raise MLBStep6CEvidenceGateError("requested_percent must be numeric") from exc
    if not math.isfinite(parsed) or parsed < 0.0:
        raise MLBStep6CEvidenceGateError("requested_percent must be finite and non-negative")
    return parsed


def evaluate_expansion_evidence(
    monitor_report: Mapping[str, Any] | None,
    *,
    requested_percent: object = MAX_EXPANSION_PERCENT,
) -> dict[str, Any]:
    """Return a fail-closed expansion decision without mutating runtime state."""
    requested_raw = _finite_percent(requested_percent)
    requested_bounded = min(requested_raw, MAX_EXPANSION_PERCENT)
    percent_bounded = requested_bounded != requested_raw
    report = dict(monitor_report or {})

    failures: list[str] = []
    warnings: list[str] = []

    if report.get("data_type") != REQUIRED_MONITOR_DATA_TYPE:
        failures.append("MONITOR_DATA_TYPE_MISMATCH")
    if report.get("schema_version") != REQUIRED_MONITOR_SCHEMA_VERSION:
        failures.append("MONITOR_SCHEMA_VERSION_MISMATCH")
    if report.get("monitor_result") != "GREEN":
        failures.append("MONITOR_NOT_GREEN")

    try:
        cycle_count = int(report.get("cycle_count", -1))
    except Exception:
        cycle_count = -1
    if cycle_count < MIN_REQUIRED_CYCLES:
        failures.append("INSUFFICIENT_MONITOR_CYCLES")

    try:
        distinct_snapshots = int(report.get("distinct_snapshot_count", -1))
    except Exception:
        distinct_snapshots = -1
    if distinct_snapshots < MIN_DISTINCT_SNAPSHOTS:
        failures.append("INSUFFICIENT_DISTINCT_SNAPSHOTS")

    try:
        max_feed_age = float(report.get("max_feed_age_seconds", math.inf))
    except Exception:
        max_feed_age = math.inf
    if not math.isfinite(max_feed_age) or max_feed_age < 0.0:
        failures.append("INVALID_FEED_AGE")
    elif max_feed_age > MAX_EXPANSION_FEED_AGE_SECONDS:
        failures.append("FEED_TOO_OLD_FOR_EXPANSION")

    try:
        stale_cycles = int(report.get("stale_cycle_count", -1))
    except Exception:
        stale_cycles = -1
    if stale_cycles != 0:
        failures.append("STALE_CYCLE_PRESENT")

    if report.get("same_slate_cohort_deterministic") is not True:
        failures.append("COHORT_NOT_DETERMINISTIC")
    if report.get("read_only_monitor") is not True:
        failures.append("MONITOR_NOT_READ_ONLY")
    if report.get("scheduled_monitor_safe") is not True:
        failures.append("SCHEDULED_MONITOR_NOT_SAFE")

    report_violations = list(report.get("violations") or [])
    if report_violations:
        failures.append("MONITOR_VIOLATIONS_PRESENT")
    report_warnings = list(report.get("warnings") or [])
    if report_warnings:
        failures.append("MONITOR_WARNINGS_PRESENT")
        warnings.extend(str(v) for v in report_warnings)

    protected_false_fields = (
        "model_math_impact",
        "pick_strength_impact",
        "ranking_math_impact",
        "risk_logic_impact",
        "wagering_impact",
        "durable_persistence",
        "wnba_impact",
    )
    for field in protected_false_fields:
        if report.get(field) is not False:
            failures.append(f"PROTECTED_FLAG_DRIFT:{field}")

    try:
        enrolled = int(report.get("total_enrolled_checks", -1))
        allow = int(report.get("total_allow_count", -1))
        block = int(report.get("total_block_count", -1))
        rollback = int(report.get("total_rollback_passthrough", -1))
    except Exception:
        enrolled = allow = block = rollback = -1

    if enrolled <= 0:
        failures.append("NO_ENROLLED_LIVE_CHECKS")
    if allow < 0 or block < 0 or allow + block != enrolled:
        failures.append("ENROLLED_GATE_PARTITION_MISMATCH")
    if rollback <= 0:
        failures.append("NO_ROLLBACK_EVIDENCE")

    failures = list(dict.fromkeys(failures))
    evidence_green = not failures

    expansion_requested = requested_bounded > CURRENT_CERTIFIED_PERCENT
    if requested_bounded <= CURRENT_CERTIFIED_PERCENT:
        permitted_percent = requested_bounded
        decision = "WITHIN_CURRENT_CERTIFIED_EXPOSURE"
        expansion_eligible = False
    elif evidence_green:
        permitted_percent = requested_bounded
        decision = "EXPANSION_ALLOWED"
        expansion_eligible = True
    else:
        permitted_percent = CURRENT_CERTIFIED_PERCENT
        decision = "HOLD_AT_10_PERCENT"
        expansion_eligible = False

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "decision": decision,
        "evidence_green": evidence_green,
        "expansion_requested": expansion_requested,
        "expansion_eligible": expansion_eligible,
        "requested_percent": requested_raw,
        "bounded_requested_percent": requested_bounded,
        "permitted_percent": permitted_percent,
        "current_certified_percent": CURRENT_CERTIFIED_PERCENT,
        "max_expansion_percent": MAX_EXPANSION_PERCENT,
        "percent_bounded": percent_bounded,
        "minimum_required_cycles": MIN_REQUIRED_CYCLES,
        "minimum_distinct_snapshots": MIN_DISTINCT_SNAPSHOTS,
        "max_expansion_feed_age_seconds": MAX_EXPANSION_FEED_AGE_SECONDS,
        "observed_cycle_count": cycle_count,
        "observed_distinct_snapshot_count": distinct_snapshots,
        "observed_max_feed_age_seconds": max_feed_age,
        "observed_stale_cycle_count": stale_cycles,
        "observed_enrolled_checks": enrolled,
        "observed_allow_count": allow,
        "observed_block_count": block,
        "observed_rollback_passthrough": rollback,
        "failures": failures,
        "warnings": warnings,
        "automatic_runtime_mutation": False,
        "requires_separate_activation_step": True,
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
    "CURRENT_CERTIFIED_PERCENT",
    "MAX_EXPANSION_PERCENT",
    "REQUIRED_MONITOR_DATA_TYPE",
    "REQUIRED_MONITOR_SCHEMA_VERSION",
    "MIN_REQUIRED_CYCLES",
    "MIN_DISTINCT_SNAPSHOTS",
    "MAX_EXPANSION_FEED_AGE_SECONDS",
    "MLBStep6CEvidenceGateError",
    "evaluate_expansion_evidence",
]
