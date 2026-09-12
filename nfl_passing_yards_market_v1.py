"""NFL Passing Yards Step 10 — post-model market evaluation.

Certified Steps 1–9 finish the projection and probability distribution before
this module sees any sportsbook information. Step 10 may compare that frozen
model output with a *verified market supplied after the model is complete*, but
it can never feed the line or price back into the projection/distribution.

The evaluator is deliberately provider-agnostic. The first UI uses manual
verified market entry because the repository has no certified NFL player-prop
provider contract. A future verified provider can call the same pure functions
without changing projection math.

Guardrails
----------
- sportsbook projection influence = exactly 0.0%
- both Over and Under prices are required for no-vig edge and a final grade
- integer passing-yard lines are push-sensitive; Step 9 is continuous and not
  discrete-push-aware, so final value grading is withheld on integer lines
- missing/malformed market data fails closed; there are no synthetic defaults
- no stake sizing and no guarantee language
"""
from __future__ import annotations

import math
from typing import Any

import nfl_passing_yards_distribution_v1 as distribution

MODEL_VERSION = "NFL PASSING YARDS STEP 10 • MARKET EVALUATION V1"


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


def _valid_american(value: Any) -> bool:
    odds = _num(value)
    return bool(_finite(odds) and odds != 0.0 and abs(odds) >= 100.0)


def american_implied_probability(odds: Any) -> float:
    odds = _num(odds)
    if not _valid_american(odds):
        return math.nan
    if odds > 0:
        return 100.0 / (odds + 100.0)
    absolute = abs(odds)
    return absolute / (absolute + 100.0)


def american_decimal_odds(odds: Any) -> float:
    odds = _num(odds)
    if not _valid_american(odds):
        return math.nan
    if odds > 0:
        return 1.0 + odds / 100.0
    return 1.0 + 100.0 / abs(odds)


def probability_to_american(probability: Any) -> float:
    p = _num(probability)
    if not _finite(p) or not (0.0 < p < 1.0):
        return math.nan
    if p >= 0.5:
        return -100.0 * p / (1.0 - p)
    return 100.0 * (1.0 - p) / p


def no_vig_two_way(over_odds: Any, under_odds: Any) -> dict:
    over_raw = american_implied_probability(over_odds)
    under_raw = american_implied_probability(under_odds)
    if not (_finite(over_raw) and _finite(under_raw)):
        return {
            "ready": False,
            "over_raw": over_raw,
            "under_raw": under_raw,
            "over_no_vig": math.nan,
            "under_no_vig": math.nan,
            "hold": math.nan,
        }
    total = over_raw + under_raw
    if total <= 0.0:
        return {
            "ready": False,
            "over_raw": over_raw,
            "under_raw": under_raw,
            "over_no_vig": math.nan,
            "under_no_vig": math.nan,
            "hold": math.nan,
        }
    return {
        "ready": True,
        "over_raw": over_raw,
        "under_raw": under_raw,
        "over_no_vig": over_raw / total,
        "under_no_vig": under_raw / total,
        "hold": total - 1.0,
    }


def expected_value_per_dollar(model_probability: Any, american_odds: Any) -> float:
    p = _num(model_probability)
    decimal = american_decimal_odds(american_odds)
    if not (_finite(p) and 0.0 <= p <= 1.0 and _finite(decimal)):
        return math.nan
    return p * (decimal - 1.0) - (1.0 - p)


def _is_integer_line(line: Any) -> bool:
    value = _num(line)
    return bool(_finite(value) and abs(value - round(value)) < 1e-9)


def grade_value(confidence: Any, edge_pp: Any, ev: Any) -> tuple[str, str]:
    """Conservative deterministic grading; never a guarantee or stake signal."""
    confidence = _safe(confidence, "CHECK").upper()
    edge = _num(edge_pp)
    ev = _num(ev)
    if not (_finite(edge) and _finite(ev)):
        return "CHECK", "market edge or EV unavailable"
    if confidence == "HIGH" and edge >= 7.5 and ev >= 0.10:
        return "A", "STRONG VALUE"
    if confidence in {"HIGH", "MEDIUM"} and edge >= 5.0 and ev >= 0.05:
        return "B", "VALUE"
    if confidence in {"HIGH", "MEDIUM", "LOW"} and edge >= 2.5 and ev > 0.0:
        return "C", "WATCH"
    return "PASS", "PASS"


def evaluate_market(
    step9: dict,
    line: Any,
    over_odds: Any = None,
    under_odds: Any = None,
    source: str = "",
    market_timestamp: str = "",
) -> dict:
    """Compare a completed Step 9 distribution with a post-model two-way market."""
    line_value = _num(line)
    over_valid = _valid_american(over_odds)
    under_valid = _valid_american(under_odds)
    result = {
        "ready": False,
        "grade_ready": False,
        "reason": "",
        "qb_name": _safe(step9.get("qb_name"), "Unresolved QB1"),
        "source": _safe(source),
        "market_timestamp": _safe(market_timestamp),
        "line": line_value,
        "over_odds": _num(over_odds),
        "under_odds": _num(under_odds),
        "model_confidence": _safe(step9.get("confidence"), "CHECK").upper(),
        "integer_line_push_risk": _is_integer_line(line_value),
        "sportsbook_projection_influence": 0.0,
        "projection_adjustment_yards": 0.0,
        "stake_sizing_enabled": False,
        "selected_side": "NONE",
        "lean": "PASS",
        "grade": "CHECK",
        "grade_label": "MARKET CHECK",
    }

    if not step9.get("ready"):
        result["reason"] = "certified Step 9 distribution is required before market evaluation"
        return result
    if not (_finite(line_value) and line_value >= 0.0):
        result["reason"] = "verified passing-yards market line is required"
        return result
    if not (over_valid or under_valid):
        result["reason"] = "at least one valid American price is required; no synthetic market price is used"
        return result

    probability = distribution.threshold_probability(
        line_value,
        step9.get("location_yards"),
        step9.get("sigma_yards"),
    )
    if not probability.get("ready"):
        result["reason"] = "Step 9 probability could not be evaluated at the offered market line"
        return result

    model_over = _num(probability.get("over_probability"))
    model_under = _num(probability.get("under_probability"))
    over_raw = american_implied_probability(over_odds) if over_valid else math.nan
    under_raw = american_implied_probability(under_odds) if under_valid else math.nan
    no_vig = no_vig_two_way(over_odds, under_odds)

    over_ev = expected_value_per_dollar(model_over, over_odds) if over_valid else math.nan
    under_ev = expected_value_per_dollar(model_under, under_odds) if under_valid else math.nan
    over_edge = 100.0 * (model_over - _num(no_vig.get("over_no_vig"))) if no_vig.get("ready") else math.nan
    under_edge = 100.0 * (model_under - _num(no_vig.get("under_no_vig"))) if no_vig.get("ready") else math.nan

    result.update({
        "ready": True,
        "reason": "",
        "model_over_probability": model_over,
        "model_under_probability": model_under,
        "model_fair_over_odds": probability_to_american(model_over),
        "model_fair_under_odds": probability_to_american(model_under),
        "raw_over_implied": over_raw,
        "raw_under_implied": under_raw,
        "no_vig_ready": bool(no_vig.get("ready")),
        "no_vig_over": no_vig.get("over_no_vig"),
        "no_vig_under": no_vig.get("under_no_vig"),
        "market_hold": no_vig.get("hold"),
        "over_edge_pp": over_edge,
        "under_edge_pp": under_edge,
        "over_ev": over_ev,
        "under_ev": under_ev,
    })

    if _is_integer_line(line_value):
        result.update({
            "reason": "integer prop line has push risk; Step 9 continuous distribution is not discrete-push-aware",
            "grade": "CHECK",
            "grade_label": "PUSH MODEL REQUIRED",
            "lean": "PASS",
        })
        return result
    if not no_vig.get("ready"):
        result.update({
            "reason": "both Over and Under prices are required for no-vig edge and final grading",
            "grade": "CHECK",
            "grade_label": "TWO-WAY PRICE REQUIRED",
            "lean": "PASS",
        })
        return result

    candidates = [
        ("OVER", over_edge, over_ev),
        ("UNDER", under_edge, under_ev),
    ]
    candidates.sort(key=lambda row: (_num(row[1]), _num(row[2])), reverse=True)
    side, edge, ev = candidates[0]
    grade, label = grade_value(result.get("model_confidence"), edge, ev)
    lean = f"LEAN {side}" if grade in {"A", "B", "C"} else "PASS"
    result.update({
        "grade_ready": True,
        "selected_side": side if grade in {"A", "B", "C"} else "NONE",
        "selected_edge_pp": edge,
        "selected_ev": ev,
        "grade": grade,
        "grade_label": label,
        "lean": lean,
        "reason": "" if grade != "PASS" else "model does not clear the conservative Step 10 value thresholds",
    })
    return result


__all__ = [
    "MODEL_VERSION",
    "american_decimal_odds",
    "american_implied_probability",
    "evaluate_market",
    "expected_value_per_dollar",
    "grade_value",
    "no_vig_two_way",
    "probability_to_american",
]
