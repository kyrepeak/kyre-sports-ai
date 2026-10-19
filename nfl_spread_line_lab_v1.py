"""NFL Spread Line Lab V1 — settlement-only regrading of the frozen MC distribution."""
from __future__ import annotations

import math
from typing import Any, Mapping

MODEL_VERSION = "NFL SPREAD LINE LAB V1 • DISTRIBUTION RE-GRADE ONLY"
MIN_SPREAD = -30.5
MAX_SPREAD = 30.5
STEP = 0.5
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MODEL_MUTATION_ALLOWED = False


def _num(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError):
        return math.nan
    return out if math.isfinite(out) else math.nan


def american_break_even(price: Any) -> float:
    value = _num(price)
    if not math.isfinite(value) or abs(value) < 1e-12:
        return math.nan
    return abs(value) / (abs(value) + 100.0) if value < 0 else 100.0 / (value + 100.0)


def _empty(error: str, selected: float | None = None) -> dict[str, Any]:
    return {
        "ready": False,
        "error": error,
        "selected_away_spread": selected,
        "sportsbook_projection_influence": 0.0,
        "model_mutated": False,
    }


def settle_line(
    analytics: Mapping[str, Any] | None,
    away_spread: Any,
    price: Any = -110,
) -> dict[str, Any]:
    """Re-grade an existing certified margin distribution at a hypothetical spread.

    The football projection and margin distribution are inputs only. This function
    never calls the model, Monte Carlo, sportsbook transport, or mutates analytics.
    """
    if not isinstance(analytics, Mapping) or not analytics.get("ready"):
        return _empty("Certified spread analytics are not ready.")

    influence = _num(analytics.get("sportsbook_projection_influence", 0.0))
    if not math.isfinite(influence) or abs(influence) > 1e-12:
        return _empty("Sportsbook/model firewall violation in analytics.")

    selected = _num(away_spread)
    if not math.isfinite(selected) or selected < MIN_SPREAD or selected > MAX_SPREAD:
        return _empty("Selected spread is outside the Line Lab range.")
    if abs(selected * 2.0 - round(selected * 2.0)) > 1e-9:
        return _empty("Selected spread must use 0.5-point increments.", selected)

    raw_distribution = analytics.get("margin_distribution")
    if not isinstance(raw_distribution, Mapping) or not raw_distribution:
        return _empty("Certified margin distribution is unavailable.", selected)

    rows: list[tuple[float, float]] = []
    for raw_margin, raw_probability in raw_distribution.items():
        margin = _num(raw_margin)
        probability = _num(raw_probability)
        if not (math.isfinite(margin) and math.isfinite(probability)) or probability < 0:
            return _empty("Certified margin distribution contains invalid values.", selected)
        rows.append((margin, probability))
    total = sum(probability for _, probability in rows)
    if not math.isfinite(total) or total <= 0:
        return _empty("Certified margin distribution has no probability mass.", selected)

    away_cover = 0.0
    home_cover = 0.0
    push = 0.0
    for margin, raw_probability in rows:
        probability = raw_probability / total
        settlement = margin + selected
        if settlement > 1e-12:
            away_cover += probability
        elif settlement < -1e-12:
            home_cover += probability
        else:
            push += probability

    non_push = max(1.0 - push, 0.0)
    away_non_push = away_cover / non_push if non_push > 1e-15 else math.nan
    home_non_push = home_cover / non_push if non_push > 1e-15 else math.nan
    break_even = american_break_even(price)
    edge = away_non_push - break_even if math.isfinite(away_non_push) and math.isfinite(break_even) else math.nan

    projected_away_margin = _num(analytics.get("projected_away_margin"))
    fair_away = -projected_away_margin if math.isfinite(projected_away_margin) else math.nan
    line_value = selected - fair_away if math.isfinite(fair_away) else math.nan

    return {
        "ready": True,
        "error": "",
        "selected_away_spread": selected,
        "selected_home_spread": -selected,
        "projected_away_margin": projected_away_margin,
        "fair_away_spread": fair_away,
        "fair_home_spread": -fair_away if math.isfinite(fair_away) else math.nan,
        "line_value": line_value,
        "away_cover_probability": away_cover,
        "home_cover_probability": home_cover,
        "push_probability": push,
        "away_cover_probability_non_push": away_non_push,
        "home_cover_probability_non_push": home_non_push,
        "break_even_probability": break_even,
        "probability_edge": edge,
        "sportsbook_projection_influence": 0.0,
        "model_mutated": False,
        "source_simulations": int(analytics.get("simulations") or 0),
        "source_certified_run": bool(analytics.get("certified_run")),
    }


__all__ = [
    "MAX_SPREAD", "MIN_SPREAD", "MODEL_MUTATION_ALLOWED", "MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP", "american_break_even", "settle_line",
]
