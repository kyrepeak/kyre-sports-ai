"""College Football Over/Under Final V1 — Step 9 selection + ranking.

Additive decision layer over permanently frozen Step-8 Over/Under Model V1.

Step 9 does not change the Step-8 projected score, projected total, or
probabilities. It applies transparent minimum-confidence rules to determine
whether a user-entered analysis line qualifies as OVER, UNDER, or PASS.

The analysis line remains a comparison threshold only and has exactly 0%
projection weight. Sportsbook feeds/prices, market-implied probabilities,
edge/EV, and Monte Carlo remain outside this model.
"""
from __future__ import annotations

from typing import Any, Mapping

MODEL_VERSION = "CFB OVER/UNDER FINAL V1 • STEP 9 SELECTION + RANKING"

MIN_SELECTION_PROBABILITY = 0.55
MIN_SELECTION_RELIABILITY = 0.72
MIN_SELECTION_COVERAGE = 0.70

A_GRADE_PROBABILITY = 0.62
B_GRADE_PROBABILITY = 0.58

ANALYSIS_LINE_PROJECTION_WEIGHT = 0.0


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _coverage_score(raw: Mapping[str, Any]) -> float:
    return _f((raw.get("feature_coverage") or {}).get("score"), 0.0)


def synthesize(
    game: Mapping[str, Any],
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply Step-9 qualification rules without altering frozen Step-8 math."""
    if not raw.get("ready"):
        return {
            "version": MODEL_VERSION,
            "ready": False,
            "reasons": list(raw.get("reasons") or ["Step 8 model is not ready"]),
            "selection": "PASS",
            "selection_ready": False,
            "rank_eligible": False,
            "analysis_line_projection_weight": ANALYSIS_LINE_PROJECTION_WEIGHT,
            "sportsbook_input_used": False,
            "market_price_used": False,
            "market_probability_used": False,
            "edge_or_ev_used": False,
            "monte_carlo_used": False,
            "empirical_calibration_claimed": False,
        }

    p_over = _f(raw.get("over_probability"))
    p_under = _f(raw.get("under_probability"))
    p_push = _f(raw.get("push_probability"))
    reliability = _f(raw.get("reliability"))
    coverage = _coverage_score(raw)

    if p_over >= p_under:
        candidate = "OVER"
        candidate_probability = p_over
    else:
        candidate = "UNDER"
        candidate_probability = p_under

    qualified = (
        candidate_probability >= MIN_SELECTION_PROBABILITY
        and reliability >= MIN_SELECTION_RELIABILITY
        and coverage >= MIN_SELECTION_COVERAGE
    )

    selection = candidate if qualified else "PASS"

    if not qualified:
        grade = "PASS"
        tier = "NO PLAY"
    elif (
        candidate_probability >= A_GRADE_PROBABILITY
        and reliability >= 0.85
        and coverage >= 0.85
    ):
        grade = "A"
        tier = "STRONG"
    elif candidate_probability >= B_GRADE_PROBABILITY:
        grade = "B"
        tier = "SOLID"
    else:
        grade = "C"
        tier = "QUALIFIED"

    conditional_no_push = 0.5
    non_push = p_over + p_under
    if non_push > 0:
        conditional_no_push = candidate_probability / non_push

    distance = abs(
        _f(raw.get("projected_total"))
        - _f(raw.get("analysis_line"))
    )

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "reasons": [],
        "selection": selection,
        "candidate_side": candidate,
        "selection_ready": qualified,
        "rank_eligible": qualified,
        "selection_probability": float(candidate_probability),
        "conditional_no_push_probability": float(conditional_no_push),
        "push_probability": float(p_push),
        "grade": grade,
        "tier": tier,
        "projected_total": _f(raw.get("projected_total")),
        "analysis_line": _f(raw.get("analysis_line")),
        "projection_line_distance": float(distance),
        "reliability": float(reliability),
        "feature_coverage": float(coverage),
        "confidence": str(raw.get("confidence") or "LOW"),
        "projected_away_points": _f(raw.get("projected_away_points")),
        "projected_home_points": _f(raw.get("projected_home_points")),
        "over_probability": float(p_over),
        "under_probability": float(p_under),
        "analysis_line_projection_weight": ANALYSIS_LINE_PROJECTION_WEIGHT,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
        "empirical_calibration_claimed": False,
        "selection_rule": {
            "minimum_probability": MIN_SELECTION_PROBABILITY,
            "minimum_reliability": MIN_SELECTION_RELIABILITY,
            "minimum_feature_coverage": MIN_SELECTION_COVERAGE,
        },
        "game_identity": str(
            game.get("identity_key") or game.get("game_id") or ""
        ),
    }


def rank_slate(
    rows: list[Mapping[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank only Step-9-qualified plays by pure model selection probability."""
    eligible: list[dict[str, Any]] = []
    for row in rows:
        final = dict(row.get("final") or {})
        if not final.get("ready") or not final.get("rank_eligible"):
            continue
        eligible.append({
            **dict(row),
            "final": final,
        })

    eligible.sort(
        key=lambda row: (
            -_f((row.get("final") or {}).get("selection_probability")),
            -_f((row.get("final") or {}).get("reliability")),
            -_f((row.get("final") or {}).get("feature_coverage")),
            str((row.get("game") or {}).get("kickoff_iso") or ""),
            str((row.get("game") or {}).get("identity_key") or ""),
        )
    )

    out = []
    for idx, row in enumerate(eligible[: max(0, int(limit))], start=1):
        item = dict(row)
        item["rank"] = idx
        out.append(item)
    return out


__all__ = [
    "ANALYSIS_LINE_PROJECTION_WEIGHT",
    "A_GRADE_PROBABILITY",
    "B_GRADE_PROBABILITY",
    "MIN_SELECTION_COVERAGE",
    "MIN_SELECTION_PROBABILITY",
    "MIN_SELECTION_RELIABILITY",
    "MODEL_VERSION",
    "rank_slate",
    "synthesize",
]
