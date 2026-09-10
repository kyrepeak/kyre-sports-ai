"""CFB Over/Under Step 7E evidence sufficiency / go-no-go layer.

Read-only decision support built on the Step 7D validation export. This module never
modifies projections, routing, market attachment, or wager selection. It fails
closed when no explicit scaling policy is supplied; thresholds are never invented.
"""
from __future__ import annotations

from typing import Any, Mapping

from cfb_over_under_validation_export_v1 import build_validation_export

EVIDENCE_VERSION = "CFB O/U EVIDENCE SUFFICIENCY V1 • STEP 7E"


class EvidenceSufficiencyError(ValueError):
    """Raised when Step 7E cannot safely evaluate scaling evidence."""


def _validate_export(payload: Mapping[str, Any]) -> None:
    diagnostics = dict(payload.get("diagnostics") or {})
    required_true = (
        "read_only",
        "live_shadow_only",
        "official_event_id_only",
        "core_model_frozen",
        "stable_json_export",
    )
    if any(diagnostics.get(key) is not True for key in required_true):
        raise EvidenceSufficiencyError("unsafe_export_diagnostics")
    if diagnostics.get("fuzzy_matching") is not False:
        raise EvidenceSufficiencyError("unsafe_fuzzy_matching")
    if diagnostics.get("synthetic_official_ids") is not False:
        raise EvidenceSufficiencyError("unsafe_synthetic_ids")
    if float(diagnostics.get("projection_weight", 0.0)) != 0.0:
        raise EvidenceSufficiencyError("unsafe_nonzero_projection_weight")
    if diagnostics.get("may_modify_projection") is not False:
        raise EvidenceSufficiencyError("unsafe_projection_mutation")


def build_evidence_summary(history_path: str) -> dict[str, Any]:
    payload = build_validation_export(history_path)
    _validate_export(payload)
    validation = dict(payload.get("validation") or {})
    overall = dict(validation.get("overall") or {})
    return {
        "version": EVIDENCE_VERSION,
        "record_count": payload.get("record_count", 0),
        "metrics": {
            "brier_score": overall.get("brier_score"),
            "mean_predicted_probability": overall.get("mean_predicted_probability"),
            "actual_rate": overall.get("actual_rate"),
            "calibration_gap": overall.get("calibration_gap"),
            "mean_clv_points": overall.get("mean_clv_points"),
            "mean_signal_edge": overall.get("mean_signal_edge"),
            "mean_closing_edge": overall.get("mean_closing_edge"),
            "mean_edge_decay": overall.get("mean_edge_decay"),
        },
        "coverage": {
            "conference_count": len(validation.get("by_conference") or {}),
            "market_type_count": len(validation.get("by_market_type") or {}),
            "calibration_bin_count": len(validation.get("calibration_curve") or []),
        },
        "decision": "POLICY_REQUIRED",
        "scaling_allowed": False,
        "reason": "No explicit scaling policy is configured; Step 7E will not invent thresholds.",
        "diagnostics": {
            "read_only": True,
            "thresholds_invented": False,
            "automatic_go_decision": False,
            "projection_weight": 0.0,
            "may_modify_projection": False,
            "core_model_frozen": True,
            "routing_changes": False,
            "wager_selection_changes": False,
        },
    }


def evaluate_with_policy(history_path: str, policy: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate only explicitly supplied thresholds; unknown/missing policy fails closed."""
    if not isinstance(policy, Mapping) or not policy:
        raise EvidenceSufficiencyError("explicit_policy_required")

    supported = {
        "min_record_count",
        "max_brier_score",
        "max_abs_calibration_gap",
        "min_mean_clv_points",
        "max_mean_edge_decay",
        "min_conference_count",
        "min_market_type_count",
    }
    unknown = set(policy) - supported
    if unknown:
        raise EvidenceSufficiencyError("unsupported_policy_key")

    summary = build_evidence_summary(history_path)
    metrics = summary["metrics"]
    coverage = summary["coverage"]
    checks: dict[str, bool] = {}

    if "min_record_count" in policy:
        checks["min_record_count"] = int(summary["record_count"]) >= int(policy["min_record_count"])
    if "max_brier_score" in policy:
        value = metrics["brier_score"]
        checks["max_brier_score"] = value is not None and float(value) <= float(policy["max_brier_score"])
    if "max_abs_calibration_gap" in policy:
        value = metrics["calibration_gap"]
        checks["max_abs_calibration_gap"] = value is not None and abs(float(value)) <= float(policy["max_abs_calibration_gap"])
    if "min_mean_clv_points" in policy:
        value = metrics["mean_clv_points"]
        checks["min_mean_clv_points"] = value is not None and float(value) >= float(policy["min_mean_clv_points"])
    if "max_mean_edge_decay" in policy:
        value = metrics["mean_edge_decay"]
        checks["max_mean_edge_decay"] = value is not None and float(value) <= float(policy["max_mean_edge_decay"])
    if "min_conference_count" in policy:
        checks["min_conference_count"] = int(coverage["conference_count"]) >= int(policy["min_conference_count"])
    if "min_market_type_count" in policy:
        checks["min_market_type_count"] = int(coverage["market_type_count"]) >= int(policy["min_market_type_count"])

    if not checks:
        raise EvidenceSufficiencyError("policy_contains_no_supported_checks")

    passed = all(checks.values())
    return {
        **summary,
        "decision": "GO" if passed else "NO_GO",
        "scaling_allowed": passed,
        "reason": "All explicit policy checks passed." if passed else "One or more explicit policy checks failed.",
        "policy": dict(policy),
        "checks": checks,
        "diagnostics": {
            **summary["diagnostics"],
            "automatic_go_decision": False,
            "explicit_policy_only": True,
        },
    }


__all__ = [
    "EVIDENCE_VERSION",
    "EvidenceSufficiencyError",
    "build_evidence_summary",
    "evaluate_with_policy",
]
