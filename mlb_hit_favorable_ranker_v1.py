"""MLB Hits Step 4 — favorable matchup gate + hit-spot ranking.

Pure post-model selection helper. It NEVER changes Hit Model V13 probabilities,
Monte Carlo outputs, candidate-pool generation, or calibration history.

It operates only on already-produced deep finalist result rows and answers:
"Of the simulated finalists, which hitters combine strong 1+ Hit probability
with a non-tough matchup and enough plate-appearance opportunity?"

A clearly tough model-relative matchup is excluded from the visible qualified
Top-5 board. If fewer than five finalists qualify, the board intentionally shows
fewer than five rather than back-filling with a tough matchup.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

RANKER_VERSION = "HIT-STEP4-FAVORABLE-RANKER-V1"

MIN_P_ONE_PLUS = 0.60
MIN_EXPECTED_AB = 3.80
TOUGH_EDGE = -0.012
FAVORABLE_EDGE = 0.012

STARTER_WEIGHT = 0.70
BULLPEN_WEIGHT = 0.30


def _f(value: Any) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def matchup_context(result: dict[str, Any]) -> dict[str, Any]:
    season_avg = _f(result.get("season_avg"))
    if season_avg is None:
        season_avg = _f(result.get("avg"))

    starter = _f(result.get("starter_rate"))
    bullpen = _f(result.get("bullpen_rate"))

    available = [x for x in (starter, bullpen) if x is not None]
    if season_avg is None or not available:
        return {
            "matchup_rate": None,
            "matchup_edge": None,
            "matchup_label": "DATA LIMITED",
        }

    if starter is not None and bullpen is not None:
        rate = STARTER_WEIGHT * starter + BULLPEN_WEIGHT * bullpen
    else:
        rate = available[0]

    edge = rate - season_avg
    if edge >= FAVORABLE_EDGE:
        label = "FAVORABLE"
    elif edge <= TOUGH_EDGE:
        label = "TOUGH"
    else:
        label = "NEUTRAL"

    return {
        "matchup_rate": rate,
        "matchup_edge": edge,
        "matchup_label": label,
    }


def _confidence_score(value: Any) -> float:
    text = str(value or "").upper()
    return {
        "HIGH": 1.00,
        "MEDIUM-HIGH": 0.85,
        "MEDIUM": 0.65,
        "LOW": 0.35,
    }.get(text, 0.45)


def hit_spot_score(result: dict[str, Any]) -> dict[str, Any]:
    sim = result.get("sim") or {}
    p1 = _f(sim.get("p_one_plus"))
    expected_ab = _f(result.get("expected_ab"))
    data_score = _f(result.get("data_score"))
    matchup = matchup_context(result)

    p_component = 0.0 if p1 is None else _clamp((p1 - 0.55) / 0.25)

    edge = _f(matchup.get("matchup_edge"))
    matchup_component = 0.50 if edge is None else _clamp((edge + 0.025) / 0.050)

    ab_component = 0.0 if expected_ab is None else _clamp((expected_ab - 3.50) / 1.20)
    data_component = 0.0 if data_score is None else _clamp(data_score / 8.0)
    lineup_component = 1.0 if bool(result.get("lineup_confirmed")) else 0.50
    confidence_component = _confidence_score(result.get("confidence"))

    score = 100.0 * (
        0.40 * p_component
        + 0.25 * matchup_component
        + 0.15 * ab_component
        + 0.08 * data_component
        + 0.07 * confidence_component
        + 0.05 * lineup_component
    )

    reasons: list[str] = []
    if matchup["matchup_label"] == "TOUGH":
        reasons.append("tough_matchup")
    if p1 is None or p1 < MIN_P_ONE_PLUS:
        reasons.append("probability_below_gate")
    if expected_ab is None or expected_ab < MIN_EXPECTED_AB:
        reasons.append("opportunity_below_gate")

    qualified = not reasons

    return {
        **matchup,
        "p_one_plus": p1,
        "expected_ab": expected_ab,
        "hit_spot_score": round(score, 1),
        "qualified": qualified,
        "gate_failures": reasons,
    }


def rank_favorable_results(
    results: Iterable[dict[str, Any]],
    limit: int = 5,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scored = []
    for index, row in enumerate(list(results or [])):
        item = dict(row or {})
        context = hit_spot_score(item)
        scored.append({
            "original_index": index,
            "result": item,
            "context": context,
        })

    qualified = [x for x in scored if x["context"]["qualified"]]
    qualified.sort(
        key=lambda x: (
            x["context"]["hit_spot_score"],
            x["context"]["p_one_plus"] or 0.0,
        ),
        reverse=True,
    )
    selected = qualified[: max(0, int(limit))]

    tough_count = sum(1 for x in scored if x["context"]["matchup_label"] == "TOUGH")
    probability_count = sum(
        1 for x in scored if "probability_below_gate" in x["context"]["gate_failures"]
    )
    opportunity_count = sum(
        1 for x in scored if "opportunity_below_gate" in x["context"]["gate_failures"]
    )

    out = []
    for rank, item in enumerate(selected, 1):
        row = dict(item["result"])
        row["_step4"] = {
            **item["context"],
            "qualified_rank": rank,
            "original_deep_rank": item["original_index"] + 1,
        }
        out.append(row)

    meta = {
        "version": RANKER_VERSION,
        "finalists_evaluated": len(scored),
        "qualified_count": len(qualified),
        "visible_count": len(out),
        "tough_excluded": tough_count,
        "probability_excluded": probability_count,
        "opportunity_excluded": opportunity_count,
        "backfilled_tough": 0,
        "probability_impact": False,
        "simulation_impact": False,
        "candidate_pool_impact": False,
        "calibration_history_impact": False,
        "visible_selection_impact": True,
        "visible_ranking_impact": True,
    }
    return out, meta


__all__ = [
    "BULLPEN_WEIGHT",
    "FAVORABLE_EDGE",
    "MIN_EXPECTED_AB",
    "MIN_P_ONE_PLUS",
    "RANKER_VERSION",
    "STARTER_WEIGHT",
    "TOUGH_EDGE",
    "hit_spot_score",
    "matchup_context",
    "rank_favorable_results",
]
