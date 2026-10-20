from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

from nfl_daily_picks_core_v1 import DailyPickCandidate
from nfl_daily_picks_ranking_v1 import normalized_pick_score

DEFAULT_RISK_MODE = "Balanced"
RISK_MODES = ("Safe", "Balanced", "Aggressive", "Max Edge")
PROBABILITY_LABEL = "estimated parlay probability"
_ALLOWED_MARKETS = frozenset({"moneyline", "spread", "game-total"})
_PENALTIES = {"LOW": 0.0, "MEDIUM": 0.03, "HIGH": 0.07, "BLOCKED": 1.0}
_MODE_BOUNDS = {
    "Safe": (2, 3),
    "Balanced": (3, 4),
    "Aggressive": (4, 5),
    "Max Edge": (2, 6),
}


def _meta(candidate: DailyPickCandidate) -> dict[str, Any]:
    try:
        return {str(key): value for key, value in tuple(candidate.metadata or ())}
    except Exception:
        return {}


def _finite_probability(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and 0.0 <= number <= 1.0


def _leg_key(candidate: DailyPickCandidate) -> tuple[str, ...]:
    line = "" if candidate.market_line is None else f"{float(candidate.market_line):.6f}"
    return (
        str(candidate.game_id),
        str(candidate.market_id),
        str(candidate.team_id),
        str(candidate.side).upper(),
        line,
    )


def _source_probability_certified(candidate: DailyPickCandidate) -> bool:
    if candidate.market_id != "game-total":
        return True
    return _meta(candidate).get("source_probability_certified") is True


def _leg_source_eligible(candidate: DailyPickCandidate) -> tuple[bool, str]:
    if candidate.market_id not in _ALLOWED_MARKETS:
        return False, "MARKET_NOT_SUPPORTED"
    if not candidate.source_ready:
        return False, "SOURCE_NOT_READY"
    if str(candidate.source_state or "").upper() != "READY":
        return False, "SOURCE_NOT_READY"
    if not _finite_probability(candidate.model_probability):
        return False, "SOURCE_PROBABILITY_INVALID"
    if candidate.market_id == "game-total" and not _source_probability_certified(candidate):
        return False, "GAME_TOTAL_PROBABILITY_NOT_SOURCE_CERTIFIED"
    try:
        age = float(candidate.source_age_seconds)
        limit = float(candidate.freshness_limit_seconds)
    except (TypeError, ValueError):
        return False, "SOURCE_FRESHNESS_INVALID"
    if not (math.isfinite(age) and math.isfinite(limit) and 0.0 <= age <= limit and limit > 0.0):
        return False, "SOURCE_STALE"
    return True, "ELIGIBLE"


def _same_game_conflict(left: DailyPickCandidate, right: DailyPickCandidate) -> str | None:
    if left.game_id != right.game_id:
        return None
    if _leg_key(left) == _leg_key(right):
        return "DUPLICATE_LEG"
    if left.market_id == right.market_id:
        if left.market_id in {"moneyline", "spread", "game-total"} and str(left.side).upper() != str(right.side).upper():
            return "DIRECT_MARKET_CONTRADICTION"
    markets = {left.market_id, right.market_id}
    if markets == {"moneyline", "spread"} and left.team_id != right.team_id:
        return "OPPOSING_TEAM_EXPOSURE"
    return None


def correlation_grade(legs: Sequence[DailyPickCandidate]) -> str:
    values = tuple(legs)
    if len(values) < 2:
        return "LOW"
    for index, left in enumerate(values):
        for right in values[index + 1 :]:
            if _same_game_conflict(left, right):
                return "BLOCKED"
    shared_games: dict[str, list[DailyPickCandidate]] = {}
    for leg in values:
        shared_games.setdefault(str(leg.game_id), []).append(leg)
    same_game_groups = [group for group in shared_games.values() if len(group) >= 2]
    if not same_game_groups:
        return "LOW"
    for group in same_game_groups:
        markets = {leg.market_id for leg in group}
        if {"moneyline", "spread"}.issubset(markets):
            teams = {leg.team_id for leg in group if leg.market_id in {"moneyline", "spread"}}
            if len(teams) == 1:
                return "HIGH"
        if len(group) >= 3:
            return "HIGH"
    return "MEDIUM"


def validate_parlay_legs(legs: Sequence[DailyPickCandidate]) -> dict[str, Any]:
    values = tuple(legs)
    if not values:
        return {"allowed": False, "reason": "NO_LEGS", "correlation_grade": "LOW"}
    seen: set[tuple[str, ...]] = set()
    for leg in values:
        eligible, reason = _leg_source_eligible(leg)
        if not eligible:
            return {"allowed": False, "reason": reason, "correlation_grade": "BLOCKED"}
        key = _leg_key(leg)
        if key in seen:
            return {"allowed": False, "reason": "DUPLICATE_LEG", "correlation_grade": "BLOCKED"}
        seen.add(key)
    for index, left in enumerate(values):
        for right in values[index + 1 :]:
            reason = _same_game_conflict(left, right)
            if reason:
                return {"allowed": False, "reason": reason, "correlation_grade": "BLOCKED"}
    return {"allowed": True, "reason": "OK", "correlation_grade": correlation_grade(values)}


def estimate_parlay_probability(legs: Sequence[DailyPickCandidate]) -> dict[str, Any]:
    validation = validate_parlay_legs(legs)
    if validation["allowed"] is not True:
        return {
            "allowed": False,
            "reason": validation["reason"],
            "correlation_grade": "BLOCKED",
            "penalty_points": 1.0,
            "estimated_probability": 0.0,
            "probability_label": PROBABILITY_LABEL,
        }
    product = 1.0
    for leg in tuple(legs):
        product *= float(leg.model_probability)
    grade = str(validation["correlation_grade"])
    penalty = _PENALTIES[grade]
    estimate = max(0.0, min(1.0, product - penalty))
    return {
        "allowed": True,
        "reason": "OK",
        "correlation_grade": grade,
        "penalty_points": penalty,
        "estimated_probability": round(estimate, 6),
        "naive_probability": round(product, 6),
        "probability_label": PROBABILITY_LABEL,
    }


def _mode_score(candidate: DailyPickCandidate, risk_mode: str) -> tuple[float, str]:
    probability = float(candidate.model_probability)
    edge = abs(float(candidate.edge_value))
    base = normalized_pick_score(candidate)
    if risk_mode == "Safe":
        score = 0.70 * probability + 0.20 * float(candidate.data_quality) + 0.10 * base
    elif risk_mode == "Aggressive":
        score = 0.42 * probability + 0.38 * base + 0.20 * min(1.0, edge / 0.10)
    elif risk_mode == "Max Edge":
        score = 0.25 * probability + 0.30 * base + 0.45 * min(1.0, edge / 0.10)
    else:
        score = 0.52 * probability + 0.30 * base + 0.18 * float(candidate.data_quality)
    return score, "|".join(_leg_key(candidate))


def build_parlay(candidates: Iterable[DailyPickCandidate], risk_mode: str = DEFAULT_RISK_MODE) -> dict[str, Any]:
    mode = risk_mode if risk_mode in RISK_MODES else DEFAULT_RISK_MODE
    minimum, maximum = _MODE_BOUNDS[mode]
    eligible = [candidate for candidate in tuple(candidates) if _leg_source_eligible(candidate)[0]]
    ordered = sorted(eligible, key=lambda candidate: (-_mode_score(candidate, mode)[0], _mode_score(candidate, mode)[1]))
    selected: list[DailyPickCandidate] = []
    for candidate in ordered:
        trial = tuple(selected + [candidate])
        validation = validate_parlay_legs(trial)
        if validation["allowed"] is not True:
            continue
        grade = validation["correlation_grade"]
        if mode == "Safe" and grade != "LOW":
            continue
        if mode == "Balanced" and grade == "HIGH":
            continue
        selected.append(candidate)
        if len(selected) >= maximum:
            break
    if len(selected) < minimum:
        return {
            "risk_mode": mode,
            "legs": tuple(selected),
            "allowed": False,
            "reason": "INSUFFICIENT_ELIGIBLE_LEGS",
            "correlation_grade": correlation_grade(tuple(selected)),
            "estimated_probability": None,
            "probability_label": PROBABILITY_LABEL,
        }
    estimate = estimate_parlay_probability(tuple(selected))
    return {
        "risk_mode": mode,
        "legs": tuple(selected),
        **estimate,
    }


__all__ = [
    "DEFAULT_RISK_MODE",
    "PROBABILITY_LABEL",
    "RISK_MODES",
    "build_parlay",
    "correlation_grade",
    "estimate_parlay_probability",
    "validate_parlay_legs",
]
