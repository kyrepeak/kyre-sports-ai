"""College Football Game Total Final V1 — Step 12 final synthesis + ranking.

Additive decision/synthesis layer over permanently frozen Step-11 Game Total
distribution.

This final layer does NOT convert Game Total into a sportsbook pick. It
qualifies the strongest independent total forecasts, assigns a transparent
forecast grade/tier, identifies the most likely total band, and produces a
slate ranking by forecast strength.

No sportsbook total, sportsbook price, market-implied probability, edge/EV,
or Monte Carlo is used.
"""
from __future__ import annotations

from typing import Any, Mapping

MODEL_VERSION = "CFB GAME TOTAL FINAL V1 • STEP 12 FINAL SYNTHESIS + RANKING"

MIN_RELIABILITY = 0.72
MIN_FEATURE_COVERAGE = 0.70
MIN_WITHIN_7_PROBABILITY = 0.30

RELIABILITY_WEIGHT = 0.45
COVERAGE_WEIGHT = 0.35
CONCENTRATION_WEIGHT = 0.20

A_GRADE_STRENGTH = 0.82
B_GRADE_STRENGTH = 0.75
C_GRADE_STRENGTH = 0.68


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _coverage_score(raw: Mapping[str, Any]) -> float:
    return _f((raw.get("feature_coverage") or {}).get("score"), 0.0)


def _within7_probability(raw: Mapping[str, Any]) -> float:
    return _f(
        ((raw.get("around_projection") or {}).get("within_7") or {}).get(
            "probability"
        ),
        0.0,
    )


def _core_range(raw: Mapping[str, Any]) -> dict[str, int]:
    percentiles = raw.get("percentiles") or {}
    return {
        "low": int(percentiles.get("p25") or 0),
        "high": int(percentiles.get("p75") or 0),
    }


def _most_likely_band(raw: Mapping[str, Any]) -> dict[str, Any]:
    bands = list(raw.get("standard_bands") or [])
    if not bands:
        return {
            "label": "—",
            "low": 0,
            "high": 0,
            "probability": 0.0,
        }
    best = max(
        bands,
        key=lambda row: (
            _f(row.get("probability")),
            -int(row.get("low") or 0),
        ),
    )
    return {
        "label": str(best.get("label") or "—"),
        "low": int(best.get("low") or 0),
        "high": int(best.get("high") or 0),
        "probability": _f(best.get("probability")),
    }


def synthesize(
    game: Mapping[str, Any],
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the final Step-12 Game Total forecast without altering Step-11 math."""
    if not raw.get("ready"):
        return {
            "version": MODEL_VERSION,
            "ready": False,
            "reasons": list(raw.get("reasons") or ["Step 11 model is not ready"]),
            "forecast_status": "PASS",
            "forecast_ready": False,
            "rank_eligible": False,
            "betting_pick_active": False,
            "sportsbook_input_used": False,
            "market_price_used": False,
            "market_probability_used": False,
            "edge_or_ev_used": False,
            "monte_carlo_used": False,
            "empirical_calibration_claimed": False,
        }

    reliability = _f(raw.get("reliability"))
    coverage = _coverage_score(raw)
    concentration = _within7_probability(raw)

    forecast_strength = (
        RELIABILITY_WEIGHT * reliability
        + COVERAGE_WEIGHT * coverage
        + CONCENTRATION_WEIGHT * concentration
    )

    qualified = (
        reliability >= MIN_RELIABILITY
        and coverage >= MIN_FEATURE_COVERAGE
        and concentration >= MIN_WITHIN_7_PROBABILITY
    )

    if not qualified:
        grade = "PASS"
        tier = "NO RANK"
        status = "PASS"
    elif forecast_strength >= A_GRADE_STRENGTH:
        grade = "A"
        tier = "ELITE FORECAST"
        status = "QUALIFIED"
    elif forecast_strength >= B_GRADE_STRENGTH:
        grade = "B"
        tier = "STRONG FORECAST"
        status = "QUALIFIED"
    else:
        grade = "C"
        tier = "QUALIFIED FORECAST"
        status = "QUALIFIED"

    i80 = raw.get("structural_interval_80") or {}
    i90 = raw.get("structural_interval_90") or {}
    core = _core_range(raw)
    band = _most_likely_band(raw)

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "reasons": [],
        "forecast_status": status,
        "forecast_ready": qualified,
        "rank_eligible": qualified,
        "grade": grade,
        "tier": tier,
        "forecast_strength": float(forecast_strength),
        "projected_combined_total": _f(raw.get("projected_combined_total")),
        "median_total": int(raw.get("median_total") or 0),
        "mode_total": int(raw.get("mode_total") or 0),
        "mode_probability": _f(raw.get("mode_probability")),
        "core_50_range": core,
        "structural_interval_80": {
            "low": int(i80.get("low") or 0),
            "high": int(i80.get("high") or 0),
        },
        "structural_interval_90": {
            "low": int(i90.get("low") or 0),
            "high": int(i90.get("high") or 0),
        },
        "most_likely_band": band,
        "within_7_probability": float(concentration),
        "reliability": float(reliability),
        "feature_coverage": float(coverage),
        "confidence": str(raw.get("confidence") or "LOW"),
        "selection_rule": {
            "minimum_reliability": MIN_RELIABILITY,
            "minimum_feature_coverage": MIN_FEATURE_COVERAGE,
            "minimum_within_7_probability": MIN_WITHIN_7_PROBABILITY,
        },
        "strength_formula": {
            "reliability_weight": RELIABILITY_WEIGHT,
            "coverage_weight": COVERAGE_WEIGHT,
            "concentration_weight": CONCENTRATION_WEIGHT,
        },
        "game_identity": str(
            game.get("identity_key") or game.get("game_id") or ""
        ),
        "final_forecast_active": True,
        "betting_pick_active": False,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
        "empirical_calibration_claimed": False,
    }


def rank_slate(
    rows: list[Mapping[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank only qualified Game Total forecasts by transparent forecast strength."""
    eligible: list[dict[str, Any]] = []

    for row in rows:
        final = dict(row.get("final") or {})
        if not final.get("ready") or not final.get("rank_eligible"):
            continue
        eligible.append({**dict(row), "final": final})

    eligible.sort(
        key=lambda row: (
            -_f((row.get("final") or {}).get("forecast_strength")),
            -_f((row.get("final") or {}).get("reliability")),
            -_f((row.get("final") or {}).get("feature_coverage")),
            -_f((row.get("final") or {}).get("within_7_probability")),
            str((row.get("game") or {}).get("kickoff_iso") or ""),
            str((row.get("game") or {}).get("identity_key") or ""),
        )
    )

    ranked: list[dict[str, Any]] = []
    for idx, row in enumerate(eligible[: max(0, int(limit))], start=1):
        item = dict(row)
        item["rank"] = idx
        ranked.append(item)
    return ranked


__all__ = [
    "A_GRADE_STRENGTH",
    "B_GRADE_STRENGTH",
    "C_GRADE_STRENGTH",
    "CONCENTRATION_WEIGHT",
    "COVERAGE_WEIGHT",
    "MIN_FEATURE_COVERAGE",
    "MIN_RELIABILITY",
    "MIN_WITHIN_7_PROBABILITY",
    "MODEL_VERSION",
    "RELIABILITY_WEIGHT",
    "rank_slate",
    "synthesize",
]
