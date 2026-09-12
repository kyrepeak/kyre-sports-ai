"""NFL Passing Yards Step 7 — transparent baseline projection.

This is the first market-independent passing-yards number in the 10-step build.
It deliberately separates volume from efficiency:

1) expected pass attempts = weighted blend of verified quarterback season volume,
   recent volume, opponent attempts allowed and team pass-attempt pace;
2) expected yards per attempt = weighted blend of verified quarterback season
   efficiency, recent efficiency and opponent season/recent efficiency allowed;
3) baseline passing yards = expected attempts * expected yards per attempt.

Step 7 does NOT use sportsbook lines, prices, market consensus or implied
probabilities. It also does not assign arbitrary numerical penalties/bonuses to
Step 4 pressure, Step 5 personnel or Step 6 weather labels. Those remain visible
context and are carried forward without pretending an unsupported effect size.

Preseason remains fail-closed because verified depth-chart QB1 identity does not
certify drives, quarters, attempts or full-game participation.
"""
from __future__ import annotations

import math
from typing import Any

MODEL_VERSION = "NFL PASSING YARDS STEP 7 • BASELINE PROJECTION V1"

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


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any):
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _ratio(numerator: Any, denominator: Any):
    num = _num(numerator)
    den = _num(denominator)
    if not (_finite(num) and _finite(den)) or den <= 0:
        return math.nan
    return num / den


def weighted_blend(values: dict[str, Any], weights: dict[str, float]) -> dict:
    """Blend only finite positive inputs and report intended-weight coverage."""
    used = []
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
        row["normalized_weight"] = row["intended_weight"] / denominator if denominator > 0 else math.nan
    return {
        "value": result,
        "coverage": coverage,
        "used": used,
        "used_count": len(used),
    }


def _coverage_grade(attempt_coverage: Any, ypa_coverage: Any) -> tuple[str, str]:
    a = _num(attempt_coverage)
    y = _num(ypa_coverage)
    if not (_finite(a) and _finite(y)):
        return "CHECK", "projection coverage unavailable"
    minimum = min(a, y)
    if minimum >= GREEN_COVERAGE:
        return "GREEN", f"attempt/efficiency source coverage at least {minimum * 100:.0f}%"
    if minimum >= MIN_READY_COVERAGE:
        return "WATCH", f"projection is usable but minimum source coverage is {minimum * 100:.0f}%"
    return "CHECK", f"minimum source coverage {minimum * 100:.0f}% is below Step 7 threshold"


def build_baseline_projection(
    qb_ctx: dict,
    qb_profile: dict,
    defense_profile: dict,
    pressure_ctx: dict,
    personnel_ctx: dict,
    environment_ctx: dict,
    side: str,
    preseason: bool = False,
) -> dict:
    """Build a sportsbook-free baseline from verified upstream evidence."""
    side = _safe(side).lower()
    qb = qb_ctx.get("qb1") or {}
    athlete_id = _safe(qb.get("athlete_id") or qb_profile.get("athlete_id"))
    defense_team_id = _safe(defense_profile.get("team_id"))

    base = {
        "ready": False,
        "reason": "",
        "qb_name": _safe(qb.get("name") or qb_profile.get("qb_name"), "Unresolved QB1"),
        "athlete_id": athlete_id,
        "opponent_team_name": _safe(defense_profile.get("team_name"), "Opponent"),
        "opponent_team_id": defense_team_id,
        "projection_yards": math.nan,
        "expected_attempts": math.nan,
        "expected_ypa": math.nan,
        "attempt_coverage": 0.0,
        "ypa_coverage": 0.0,
        "coverage_grade": "CHECK",
        "coverage_basis": "projection not built",
        "pressure_context": _safe(pressure_ctx.get("pressure_label"), "CHECK"),
        "personnel_context": _safe(personnel_ctx.get("personnel_label"), "CHECK"),
        "environment_context": _safe(environment_ctx.get("environment_label"), "CHECK"),
        "weather_context": _safe(environment_ctx.get("weather_label"), "CHECK"),
        "context_adjustment_yards": 0.0,
        "sportsbook_influence": 0.0,
        "monte_carlo_enabled": False,
    }

    if preseason:
        base["reason"] = "preseason workload is not certified for a full-game passing-yards projection"
        return base
    if not athlete_id.isdigit():
        base["reason"] = "verified ESPN quarterback athlete ID is required"
        return base
    if not defense_team_id.isdigit():
        base["reason"] = "verified ESPN opponent team ID is required"
        return base
    if not qb_profile.get("ready"):
        base["reason"] = "verified quarterback season passing profile is required"
        return base
    if not defense_profile.get("ready"):
        base["reason"] = "verified opponent pass-defense profile is required"
        return base

    season = qb_profile.get("season") or {}
    defense_season = defense_profile.get("season") or {}
    pace = environment_ctx.get(f"{side}_pace") or {}

    recent3_attempts = _num(qb_profile.get("recent3_attempts"))
    recent3_yards = _num(qb_profile.get("recent3_yards"))
    recent3_ypa = _ratio(recent3_yards, recent3_attempts)

    attempt_inputs = {
        "qb_season_attempts_per_game": season.get("attempts_per_game"),
        "qb_recent3_attempts": recent3_attempts,
        "opponent_attempts_allowed_per_game": defense_season.get("passing_attempts_allowed_per_game"),
        "team_pass_attempts_per_game": pace.get("pass_attempts_per_game"),
    }
    ypa_inputs = {
        "qb_season_ypa": season.get("yards_per_attempt"),
        "qb_recent3_ypa": recent3_ypa,
        "opponent_season_ypa_allowed": defense_season.get("yards_per_attempt_allowed"),
        "opponent_recent3_ypa_allowed": defense_profile.get("recent3_ypa_allowed"),
    }

    attempt_blend = weighted_blend(attempt_inputs, ATTEMPT_WEIGHTS)
    ypa_blend = weighted_blend(ypa_inputs, YPA_WEIGHTS)
    expected_attempts = _num(attempt_blend.get("value"))
    expected_ypa = _num(ypa_blend.get("value"))
    projection = expected_attempts * expected_ypa if _finite(expected_attempts) and _finite(expected_ypa) else math.nan

    grade, grade_basis = _coverage_grade(attempt_blend.get("coverage"), ypa_blend.get("coverage"))
    ready = bool(
        _finite(projection)
        and projection > 0
        and _num(attempt_blend.get("coverage")) >= MIN_READY_COVERAGE
        and _num(ypa_blend.get("coverage")) >= MIN_READY_COVERAGE
    )

    base.update({
        "ready": ready,
        "reason": "" if ready else "insufficient verified volume or efficiency coverage for Step 7 baseline",
        "projection_yards": projection,
        "expected_attempts": expected_attempts,
        "expected_ypa": expected_ypa,
        "attempt_coverage": attempt_blend.get("coverage"),
        "ypa_coverage": ypa_blend.get("coverage"),
        "coverage_grade": grade,
        "coverage_basis": grade_basis,
        "attempt_inputs": attempt_inputs,
        "ypa_inputs": ypa_inputs,
        "attempt_components": attempt_blend.get("used") or [],
        "ypa_components": ypa_blend.get("used") or [],
        "formula": "expected_attempts × expected_yards_per_attempt",
        "context_state": "PRESSURE/PERSONNEL/ENVIRONMENT DISPLAYED BUT NOT NUMERICALLY ADJUSTED IN STEP 7",
    })
    return base


__all__ = [
    "ATTEMPT_WEIGHTS",
    "GREEN_COVERAGE",
    "MIN_READY_COVERAGE",
    "MODEL_VERSION",
    "YPA_WEIGHTS",
    "build_baseline_projection",
    "weighted_blend",
]
