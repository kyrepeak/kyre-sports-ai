"""MLB Step 6D controlled production expansion from 10% to 25%.

Step 6C certified that a fresh four-snapshot Step 6B monitor window permits a
25% full-game MLB price-gate cohort. Step 6D is the separate activation boundary
required by that certification. It consumes a Step 6C permission mapping and,
when that permission is valid, supplies a production default of ON at 25% to the
already-certified Step 5.10 deterministic game cohort controller.

Safety precedence:
1. global kill switch -> exact Step 5 pass-through (0%)
2. Streamlit session rollback -> exact Step 5 pass-through (0%)
3. invalid/missing Step 6C expansion permission -> hold at certified 10%
4. explicit host configuration -> bounded to 25%
5. repository production default -> ON at 25%

This policy never changes model probability, Pick Strength, ranking math, risk
logic, persistence, wagering, player-prop price gating, or WNBA behavior.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

DATA_TYPE = "mlb_step6d_production_expansion_v1"
SCHEMA_VERSION = 1
CURRENT_CERTIFIED_BASELINE_PERCENT = 10.0
DEFAULT_ENABLED = True
DEFAULT_PERCENT = 25.0
MAX_PRODUCTION_CANARY_PERCENT = 25.0

ENABLED_ENV_KEY = "MLB_STEP6D_PRODUCTION_CANARY_ENABLED"
PERCENT_ENV_KEY = "MLB_STEP6D_PRODUCTION_CANARY_PERCENT"
KILL_SWITCH_ENV_KEY = "MLB_STEP6D_PRODUCTION_CANARY_KILL_SWITCH"
ROLLBACK_QUERY_KEY = "mlb_step6d_rollback"

STEP6C_CERTIFIED_MAIN_SHA = "b75fe13a25c15808c613d7ab2679d7bb0a829255"
STEP6C_CERTIFICATION_RUN_ID = 33416917835
STEP6C_CERTIFICATION_MARKER = "MLB_STEP6C_EVIDENCE_GATED_EXPANSION_GREEN"

_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}

# Release attestation captured from the GREEN Step 6C live certification. This
# is not a substitute for ongoing monitoring: Step 6B and Step 6D scheduled
# monitors continue to evaluate fresh market state after activation.
CERTIFIED_STEP6C_PERMISSION: dict[str, Any] = {
    "data_type": "mlb_step6c_evidence_gate_v1",
    "schema_version": 1,
    "decision": "EXPANSION_ALLOWED",
    "evidence_green": True,
    "expansion_eligible": True,
    "permitted_percent": 25.0,
    "current_certified_percent": 10.0,
    "max_expansion_percent": 25.0,
    "observed_cycle_count": 4,
    "observed_distinct_snapshot_count": 4,
    "observed_max_feed_age_seconds": 4.222663,
    "observed_stale_cycle_count": 0,
    "observed_enrolled_checks": 24,
    "observed_allow_count": 8,
    "observed_block_count": 16,
    "observed_rollback_passthrough": 288,
    "failures": [],
    "warnings": [],
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


class MLBStep6DProductionExpansionError(ValueError):
    pass


def _parse_bool(value: object, *, default: bool) -> tuple[bool, bool]:
    if value is None:
        return default, True
    text = str(value).strip().lower()
    if text in _TRUE_VALUES:
        return True, True
    if text in _FALSE_VALUES:
        return False, True
    return default, False


def _bounded_percent(value: object, *, default: float) -> tuple[float, bool, bool]:
    if value is None or str(value).strip() == "":
        raw = float(default)
        valid = True
    elif isinstance(value, bool):
        raw = 0.0
        valid = False
    else:
        try:
            raw = float(value)
            valid = math.isfinite(raw) and raw >= 0.0
        except Exception:
            raw = 0.0
            valid = False
    if not valid:
        raw = 0.0
    bounded = max(0.0, min(MAX_PRODUCTION_CANARY_PERCENT, raw))
    return bounded, valid, abs(bounded - raw) > 1e-12


def validate_step6c_permission(permission: Mapping[str, Any] | None) -> tuple[bool, list[str]]:
    """Validate that a Step 6C decision actually permits the 25% activation."""
    report = dict(permission or {})
    failures: list[str] = []
    if report.get("data_type") != "mlb_step6c_evidence_gate_v1":
        failures.append("STEP6C_DATA_TYPE_MISMATCH")
    if report.get("schema_version") != 1:
        failures.append("STEP6C_SCHEMA_VERSION_MISMATCH")
    if report.get("decision") != "EXPANSION_ALLOWED":
        failures.append("STEP6C_DECISION_NOT_ALLOWED")
    if report.get("evidence_green") is not True:
        failures.append("STEP6C_EVIDENCE_NOT_GREEN")
    if report.get("expansion_eligible") is not True:
        failures.append("STEP6C_EXPANSION_NOT_ELIGIBLE")
    try:
        permitted = float(report.get("permitted_percent", math.nan))
    except Exception:
        permitted = math.nan
    if not math.isfinite(permitted) or permitted < DEFAULT_PERCENT:
        failures.append("STEP6C_PERMISSION_BELOW_25")
    if list(report.get("failures") or []):
        failures.append("STEP6C_FAILURES_PRESENT")
    if list(report.get("warnings") or []):
        failures.append("STEP6C_WARNINGS_PRESENT")
    if report.get("automatic_runtime_mutation") is not False:
        failures.append("STEP6C_RUNTIME_MUTATION_CONTRACT_DRIFT")
    if report.get("requires_separate_activation_step") is not True:
        failures.append("STEP6C_SEPARATE_ACTIVATION_CONTRACT_DRIFT")
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
            failures.append(f"STEP6C_PROTECTED_FLAG_DRIFT:{field}")
    return (not failures), list(dict.fromkeys(failures))


def resolve_step6d_production_expansion(
    env: Mapping[str, str] | None = None,
    *,
    rollback_requested: bool = False,
    permission: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve Step 6D activation without mutating any external state."""
    env = dict(env or {})
    supplied_permission = permission is not None
    permission_map = dict(CERTIFIED_STEP6C_PERMISSION if permission is None else permission)
    permission_valid, permission_failures = validate_step6c_permission(permission_map)
    permission_source = "EXTERNAL_RUNTIME_PERMISSION" if supplied_permission else "CERTIFIED_RELEASE_ATTESTATION"

    kill, kill_valid = _parse_bool(env.get(KILL_SWITCH_ENV_KEY), default=False)
    host_present = any(key in env for key in (ENABLED_ENV_KEY, PERCENT_ENV_KEY, KILL_SWITCH_ENV_KEY))

    common = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "production_default_enabled": DEFAULT_ENABLED,
        "production_default_percent": DEFAULT_PERCENT,
        "current_certified_baseline_percent": CURRENT_CERTIFIED_BASELINE_PERCENT,
        "max_production_canary_percent": MAX_PRODUCTION_CANARY_PERCENT,
        "step6c_permission_valid": permission_valid,
        "step6c_permission_failures": permission_failures,
        "step6c_permission_source": permission_source,
        "step6c_certified_main_sha": STEP6C_CERTIFIED_MAIN_SHA,
        "step6c_certification_run_id": STEP6C_CERTIFICATION_RUN_ID,
        "step6c_certification_marker": STEP6C_CERTIFICATION_MARKER,
        "exact_rollback": True,
        "host_control_present": host_present,
        "rollback_requested": bool(rollback_requested),
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "player_props_price_gated": False,
        "wnba_impact": False,
    }

    if kill:
        return {
            **common,
            "enabled": False,
            "requested_percent": 0.0,
            "effective_percent": 0.0,
            "control_source": "GLOBAL_KILL_SWITCH",
            "config_valid": kill_valid,
            "percent_bounded": False,
        }

    if rollback_requested:
        return {
            **common,
            "enabled": False,
            "requested_percent": 0.0,
            "effective_percent": 0.0,
            "control_source": "STREAMLIT_SESSION_ROLLBACK",
            "config_valid": True,
            "percent_bounded": False,
        }

    # If the expansion permission is missing or degraded, preserve the already
    # certified 10% Step 6A baseline instead of expanding.
    if not permission_valid:
        return {
            **common,
            "enabled": True,
            "requested_percent": CURRENT_CERTIFIED_BASELINE_PERCENT,
            "effective_percent": CURRENT_CERTIFIED_BASELINE_PERCENT,
            "control_source": "STEP6C_PERMISSION_HOLD",
            "config_valid": False,
            "percent_bounded": False,
        }

    if host_present:
        enabled, enabled_valid = _parse_bool(env.get(ENABLED_ENV_KEY), default=DEFAULT_ENABLED)
        percent, percent_valid, bounded = _bounded_percent(env.get(PERCENT_ENV_KEY), default=DEFAULT_PERCENT)
        valid = bool(enabled_valid and percent_valid and kill_valid)
        if not valid:
            enabled = False
            percent = 0.0
        if not enabled or percent <= 0.0:
            enabled = False
            percent = 0.0
        return {
            **common,
            "enabled": enabled,
            "requested_percent": percent,
            "effective_percent": percent,
            "control_source": "HOST_ENV",
            "config_valid": valid,
            "percent_bounded": bounded,
        }

    return {
        **common,
        "enabled": DEFAULT_ENABLED,
        "requested_percent": DEFAULT_PERCENT,
        "effective_percent": DEFAULT_PERCENT,
        "control_source": "REPOSITORY_PRODUCTION_DEFAULT",
        "config_valid": True,
        "percent_bounded": False,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "CURRENT_CERTIFIED_BASELINE_PERCENT",
    "DEFAULT_ENABLED",
    "DEFAULT_PERCENT",
    "MAX_PRODUCTION_CANARY_PERCENT",
    "ENABLED_ENV_KEY",
    "PERCENT_ENV_KEY",
    "KILL_SWITCH_ENV_KEY",
    "ROLLBACK_QUERY_KEY",
    "STEP6C_CERTIFIED_MAIN_SHA",
    "STEP6C_CERTIFICATION_RUN_ID",
    "STEP6C_CERTIFICATION_MARKER",
    "CERTIFIED_STEP6C_PERMISSION",
    "MLBStep6DProductionExpansionError",
    "validate_step6c_permission",
    "resolve_step6d_production_expansion",
]
