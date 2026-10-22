"""Provider-neutral NFL Passing Yards projection parity layer.

V2 preserves the certified Step-7 numeric formula exactly while accepting
canonical Kyre inputs instead of provider-specific identities. Data acquisition
belongs to Kyre Sports API; this module is pure math.
"""
from __future__ import annotations

import math
from typing import Any

ATTEMPT_WEIGHTS = {
    "qb_season_attempts_per_game": 0.45,
    "qb_recent3_attempts": 0.20,
    "opponent_attempts_allowed_per_game": 0.20,
    "team_pass_attempts_per_game": 0.15,
}
YPA_WEIGHTS = {
    "qb_season_ypa": 0.45,
    "qb_recent3_ypa": 0.20,
    "opponent_season_ypa_allowed": 0.25,
    "opponent_recent3_ypa_allowed": 0.10,
}
MIN_READY_COVERAGE = 0.65
GREEN_COVERAGE = 0.85


def _num(value: Any) -> float:
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def weighted_blend(values: dict[str, Any], weights: dict[str, float]) -> dict[str, Any]:
    used: list[dict[str, float | str]] = []
    numerator = 0.0
    denominator = 0.0
    coverage = 0.0
    for key, weight in weights.items():
        value = _num(values.get(key))
        if not _finite(value) or value <= 0:
            continue
        w = float(weight)
        numerator += value * w
        denominator += w
        coverage += w
        used.append({"key": key, "value": value, "intended_weight": w})
    result = numerator / denominator if denominator > 0 else math.nan
    for row in used:
        row["normalized_weight"] = float(row["intended_weight"]) / denominator if denominator > 0 else math.nan
    return {"value": result, "coverage": coverage, "used": used, "used_count": len(used)}


def project_from_canonical_inputs(
    attempt_values: dict[str, Any],
    ypa_values: dict[str, Any],
) -> dict[str, Any]:
    """Run the frozen formula on normalized provider-neutral values."""
    attempts = weighted_blend(attempt_values, ATTEMPT_WEIGHTS)
    ypa = weighted_blend(ypa_values, YPA_WEIGHTS)
    expected_attempts = _num(attempts.get("value"))
    expected_ypa = _num(ypa.get("value"))
    projection = expected_attempts * expected_ypa if _finite(expected_attempts) and _finite(expected_ypa) else math.nan
    ready = bool(
        _finite(projection)
        and projection > 0
        and float(attempts.get("coverage") or 0.0) >= MIN_READY_COVERAGE
        and float(ypa.get("coverage") or 0.0) >= MIN_READY_COVERAGE
    )
    minimum = min(float(attempts.get("coverage") or 0.0), float(ypa.get("coverage") or 0.0))
    grade = "GREEN" if minimum >= GREEN_COVERAGE else ("WATCH" if minimum >= MIN_READY_COVERAGE else "CHECK")
    return {
        "ready": ready,
        "projection_yards": projection,
        "expected_attempts": expected_attempts,
        "expected_ypa": expected_ypa,
        "attempt_coverage": attempts.get("coverage"),
        "ypa_coverage": ypa.get("coverage"),
        "coverage_grade": grade,
        "attempt_components": attempts.get("used") or [],
        "ypa_components": ypa.get("used") or [],
        "formula": "expected_attempts × expected_yards_per_attempt",
        "sportsbook_influence": 0.0,
    }


__all__ = ["ATTEMPT_WEIGHTS", "YPA_WEIGHTS", "MIN_READY_COVERAGE", "GREEN_COVERAGE", "project_from_canonical_inputs", "weighted_blend"]
