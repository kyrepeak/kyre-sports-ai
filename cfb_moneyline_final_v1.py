"""College Football Moneyline Final Synthesis V1 — Step 6.

Additive final-probability layer over permanently frozen Moneyline Model V1.

Important calibration definition
--------------------------------
This module performs STRUCTURAL calibration only. It is not fitted to
sportsbook prices and does not claim historical empirical calibration.

The frozen Step-5 raw P(win) is transformed conservatively toward 50% with a
transparent reliability/coverage/sample-aware temperature. The result is the
final Step-6 model probability used for fair model odds and slate ranking.

Sportsbook market probability weight remains exactly 0%.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

MODEL_VERSION = "CFB MONEYLINE FINAL V1 • STEP 6 STRUCTURAL CALIBRATION"

CALIBRATION_METHOD = "STRUCTURAL_RELIABILITY_TEMPERATURE_V1"
MARKET_WEIGHT = 0.0

_MIN_FINAL_P = 0.04
_MAX_FINAL_P = 0.96
_MIN_TEMPERATURE = 1.00
_MAX_TEMPERATURE = 1.65

_CONFIDENCE_PENALTY = {
    "HIGH": 0.00,
    "MEDIUM": 0.05,
    "LOW": 0.12,
}

_GRADE_ORDER = {
    "A+": 5,
    "A": 4,
    "B+": 3,
    "B": 2,
    "C": 1,
    "PASS": 0,
}


def _f(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return x if math.isfinite(x) else float(default)
    except (TypeError, ValueError, OverflowError):
        return float(default)


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _logit(p: float) -> float:
    q = _clamp(float(p), 1e-9, 1.0 - 1e-9)
    return math.log(q / (1.0 - q))


def _logistic(x: float) -> float:
    z = _clamp(float(x), -30.0, 30.0)
    return 1.0 / (1.0 + math.exp(-z))


def _coverage_score(raw: Mapping[str, Any]) -> float:
    return _clamp(
        _f((raw.get("feature_coverage") or {}).get("score"), 0.0),
        0.0,
        1.0,
    )


def _calibration_temperature(raw: Mapping[str, Any]) -> float:
    reliability = _clamp(_f(raw.get("reliability"), 0.55), 0.0, 1.0)
    coverage = _coverage_score(raw)
    sample = _clamp(_f(raw.get("sample_factor"), 0.0), 0.0, 1.0)
    confidence = str(raw.get("confidence") or "LOW").upper()
    penalty = _CONFIDENCE_PENALTY.get(confidence, _CONFIDENCE_PENALTY["LOW"])

    temperature = (
        1.0
        + 0.35 * (1.0 - reliability)
        + 0.30 * (1.0 - coverage)
        + 0.20 * (1.0 - sample)
        + penalty
    )
    return _clamp(temperature, _MIN_TEMPERATURE, _MAX_TEMPERATURE)


def _calibrated_probability(raw_probability: float, temperature: float) -> float:
    p = _logistic(_logit(raw_probability) / float(temperature))
    return _clamp(p, _MIN_FINAL_P, _MAX_FINAL_P)


def _american_odds(probability: float) -> int:
    p = _clamp(float(probability), 1e-9, 1.0 - 1e-9)
    if p >= 0.5:
        return int(round(-100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


def _probability_uncertainty(
    raw: Mapping[str, Any],
    final_probability: float,
) -> dict[str, float]:
    reliability = _clamp(_f(raw.get("reliability"), 0.55), 0.0, 1.0)
    coverage = _coverage_score(raw)
    sample = _clamp(_f(raw.get("sample_factor"), 0.0), 0.0, 1.0)

    sigma = (
        0.035
        + 0.070 * (1.0 - reliability)
        + 0.060 * (1.0 - coverage)
        + 0.040 * (1.0 - sample)
    )
    sigma = _clamp(sigma, 0.035, 0.160)
    half90 = 1.645 * sigma
    return {
        "sigma": sigma,
        "p90_low": _clamp(final_probability - half90, 0.01, 0.99),
        "p90_high": _clamp(final_probability + half90, 0.01, 0.99),
    }


def _margin_uncertainty(raw: Mapping[str, Any]) -> dict[str, float]:
    reliability = _clamp(_f(raw.get("reliability"), 0.55), 0.0, 1.0)
    coverage = _coverage_score(raw)
    sample = _clamp(_f(raw.get("sample_factor"), 0.0), 0.0, 1.0)
    margin = _f(raw.get("projected_margin_home_raw"), 0.0)

    sigma = 12.0 + 5.0 * (1.0 - reliability) + 3.0 * (1.0 - coverage) + 2.0 * (1.0 - sample)
    half90 = 1.645 * sigma
    return {
        "sigma_points": sigma,
        "margin90_low": margin - half90,
        "margin90_high": margin + half90,
    }


def _model_grade(
    winner_probability: float,
    reliability: float,
    coverage: float,
) -> tuple[str, str]:
    p = float(winner_probability)
    rel = float(reliability)
    cov = float(coverage)

    if p >= 0.75 and rel >= 0.85 and cov >= 0.80:
        return "A+", "TOP TIER"
    if p >= 0.70 and rel >= 0.78 and cov >= 0.70:
        return "A", "STRONG"
    if p >= 0.65 and rel >= 0.70 and cov >= 0.60:
        return "B+", "SOLID"
    if p >= 0.60:
        return "B", "WATCH"
    if p >= 0.55:
        return "C", "LEAN"
    return "PASS", "PASS"


def synthesize(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the Step-6 final model result from a frozen Step-5 raw output."""
    if not raw.get("ready") or not raw.get("raw_probability_ready"):
        return {
            "version": MODEL_VERSION,
            "ready": False,
            "reasons": list(raw.get("reasons") or ["raw Step-5 model is not ready"]),
            "calibration_method": CALIBRATION_METHOD,
            "market_weight": MARKET_WEIGHT,
            "market_probability_used": False,
            "empirical_backtest_calibrated": False,
            "fair_moneyline_ready": False,
            "final_pick_ready": False,
        }

    raw_home = _clamp(_f(raw.get("home_win_probability_raw"), 0.5), 0.001, 0.999)
    temperature = _calibration_temperature(raw)
    final_home = _calibrated_probability(raw_home, temperature)
    final_away = 1.0 - final_home

    if final_home >= final_away:
        winner_side = "home"
        winner_team = str(home.get("team") or game.get("home_team") or "Home")
        winner_probability = final_home
    else:
        winner_side = "away"
        winner_team = str(away.get("team") or game.get("away_team") or "Away")
        winner_probability = final_away

    reliability = _clamp(_f(raw.get("reliability"), 0.55), 0.0, 1.0)
    coverage = _coverage_score(raw)
    grade, tier = _model_grade(winner_probability, reliability, coverage)

    home_uncertainty = _probability_uncertainty(raw, final_home)
    away_uncertainty = {
        "sigma": home_uncertainty["sigma"],
        "p90_low": 1.0 - home_uncertainty["p90_high"],
        "p90_high": 1.0 - home_uncertainty["p90_low"],
    }
    margin_uncertainty = _margin_uncertainty(raw)

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "reasons": [],
        "calibration_method": CALIBRATION_METHOD,
        "calibration_temperature": float(temperature),
        "market_weight": MARKET_WEIGHT,
        "market_probability_used": False,
        "empirical_backtest_calibrated": False,
        "home_win_probability_final": float(final_home),
        "away_win_probability_final": float(final_away),
        "home_fair_moneyline": _american_odds(final_home),
        "away_fair_moneyline": _american_odds(final_away),
        "fair_moneyline_ready": True,
        "winner_side": winner_side,
        "winner_team": winner_team,
        "winner_probability_final": float(winner_probability),
        "model_grade": grade,
        "model_tier": tier,
        "final_pick_ready": True,
        "projected_home_points": _f(raw.get("projected_home_points_raw"), 0.0),
        "projected_away_points": _f(raw.get("projected_away_points_raw"), 0.0),
        "projected_margin_home": _f(raw.get("projected_margin_home_raw"), 0.0),
        "projected_total": _f(raw.get("projected_total_raw"), 0.0),
        "reliability": reliability,
        "sample_factor": _clamp(_f(raw.get("sample_factor"), 0.0), 0.0, 1.0),
        "feature_coverage": coverage,
        "input_confidence": str(raw.get("confidence") or "LOW").upper(),
        "home_probability_uncertainty": home_uncertainty,
        "away_probability_uncertainty": away_uncertainty,
        "margin_uncertainty": margin_uncertainty,
        "raw_home_probability": raw_home,
        "raw_away_probability": 1.0 - raw_home,
        "raw_model_version": str(raw.get("version") or ""),
    }


def rank_slate(rows: Iterable[Mapping[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Rank ready Step-6 game outputs by pure final win probability.

    Sportsbook price/value is intentionally absent from the ranking contract.
    """
    ready: list[dict[str, Any]] = []
    for item in rows:
        final = item.get("final") or {}
        if not final.get("ready"):
            continue
        row = dict(item)
        row["rank_probability"] = _f(final.get("winner_probability_final"), 0.0)
        row["rank_grade"] = _GRADE_ORDER.get(str(final.get("model_grade") or "PASS"), 0)
        row["rank_reliability"] = _f(final.get("reliability"), 0.0)
        row["rank_coverage"] = _f(final.get("feature_coverage"), 0.0)
        ready.append(row)

    ready.sort(
        key=lambda x: (
            -x["rank_probability"],
            -x["rank_grade"],
            -x["rank_reliability"],
            -x["rank_coverage"],
            str((x.get("game") or {}).get("kickoff_iso") or ""),
            str((x.get("game") or {}).get("identity_key") or ""),
        )
    )

    out: list[dict[str, Any]] = []
    for idx, row in enumerate(ready[: max(0, int(limit))], start=1):
        result = dict(row)
        result["rank"] = idx
        out.append(result)
    return out


__all__ = [
    "CALIBRATION_METHOD",
    "MARKET_WEIGHT",
    "MODEL_VERSION",
    "_american_odds",
    "_calibrated_probability",
    "_calibration_temperature",
    "_model_grade",
    "rank_slate",
    "synthesize",
]
