"""NFL Passing Yards Step 9 — outcome distribution + probability engine.

Step 8 produced a sportsbook-free contextual central projection plus a
transparent uncertainty layer. Step 9 converts only *observed recent QB game
variability* into a probability distribution. It deliberately does not reinterpret
Step 8's source-disagreement envelope as a confidence interval.

Probability model
-----------------
- location = certified Step 8 contextual passing-yards projection
- scale = verified recent-game passing-yard sample standard deviation
- minimum sample = 3 verified recent games (up to the 5 already used in Step 8)
- support = passing yards >= 0, implemented as a zero-truncated normal model
- probabilities and quantiles are computed analytically with ``statistics.NormalDist``
  rather than Monte Carlo, so there is no simulation sampling error or random seed.

This is an explicit model assumption, not a claim that NFL passing yards are
perfectly normal. With fewer than three verified recent games, zero/invalid
observed variance, a withheld Step 8 projection, or preseason workload, the
probability engine fails closed.

No sportsbook line, price, market consensus, implied probability, no-vig input,
fair odds, EV, ranking or recommendation enters Step 9. Sportsbook influence on
the projection remains exactly 0.0%.
"""
from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any, Iterable

MODEL_VERSION = "NFL PASSING YARDS STEP 9 • DISTRIBUTION + PROBABILITY V1"
DEFAULT_THRESHOLDS = (150, 175, 200, 225, 250, 275, 300, 325, 350, 375, 400)
MIN_RECENT_GAMES = 3
MIN_SIGMA_YARDS = 1e-9


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


def _clamp_probability(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _recent_scale(step8: dict) -> dict:
    uncertainty = step8.get("uncertainty") or {}
    recent = uncertainty.get("recent") or {}
    games = int(_num(recent.get("games"))) if _finite(recent.get("games")) else 0
    sigma = _num(recent.get("sample_std_yards"))
    ready = bool(games >= MIN_RECENT_GAMES and _finite(sigma) and sigma > MIN_SIGMA_YARDS)
    return {
        "ready": ready,
        "games": games,
        "sigma_yards": sigma,
        "basis": (
            f"last {games} verified QB games sample SD"
            if ready
            else f"needs at least {MIN_RECENT_GAMES} verified recent games with non-zero observed variance"
        ),
    }


def truncated_normal_cdf(x: Any, location: Any, sigma: Any) -> float:
    """CDF of N(location, sigma) conditional on X >= 0."""
    x = _num(x)
    location = _num(location)
    sigma = _num(sigma)
    if not (_finite(x) and _finite(location) and _finite(sigma)) or sigma <= 0:
        return math.nan
    if x <= 0:
        return 0.0
    dist = NormalDist(mu=location, sigma=sigma)
    lower_mass = dist.cdf(0.0)
    survivor_at_zero = 1.0 - lower_mass
    if survivor_at_zero <= 0.0:
        return math.nan
    value = (dist.cdf(x) - lower_mass) / survivor_at_zero
    return _clamp_probability(value)


def truncated_normal_quantile(probability: Any, location: Any, sigma: Any) -> float:
    """Inverse CDF for the zero-truncated normal model."""
    p = _num(probability)
    location = _num(location)
    sigma = _num(sigma)
    if not (_finite(p) and _finite(location) and _finite(sigma)) or sigma <= 0 or not (0.0 < p < 1.0):
        return math.nan
    dist = NormalDist(mu=location, sigma=sigma)
    lower_mass = dist.cdf(0.0)
    survivor_at_zero = 1.0 - lower_mass
    if survivor_at_zero <= 0.0:
        return math.nan
    target = lower_mass + p * survivor_at_zero
    # Guard NormalDist.inv_cdf from floating-point endpoint spillover.
    target = max(1e-12, min(1.0 - 1e-12, target))
    return max(0.0, dist.inv_cdf(target))


def threshold_probability(threshold: Any, location: Any, sigma: Any) -> dict:
    threshold = _num(threshold)
    if not _finite(threshold):
        return {"ready": False, "threshold": math.nan, "over_probability": math.nan, "under_probability": math.nan}
    cdf = truncated_normal_cdf(threshold, location, sigma)
    if not _finite(cdf):
        return {"ready": False, "threshold": threshold, "over_probability": math.nan, "under_probability": math.nan}
    under = _clamp_probability(cdf)
    over = _clamp_probability(1.0 - under)
    return {
        "ready": True,
        "threshold": threshold,
        "over_probability": over,
        "under_probability": under,
    }


def probability_confidence(step8: dict, games: int) -> tuple[str, str]:
    """Evidence-quality label, explicitly not a probability-of-correctness score."""
    upstream = _safe(step8.get("confidence"), "CHECK").upper()
    if upstream == "CHECK" or games < MIN_RECENT_GAMES:
        return "CHECK", "Step 8 evidence or recent-variance sample is insufficient"
    if upstream == "HIGH" and games >= 5:
        return "HIGH", "Step 8 confidence HIGH with five verified recent games informing observed variance"
    if upstream in {"HIGH", "MEDIUM"} and games >= 4:
        return "MEDIUM", f"Step 8 confidence {upstream} with {games} verified recent games informing observed variance"
    return "LOW", f"probability shape is based on only {games} verified recent games and/or Step 8 confidence {upstream}"


def build_distribution(step8: dict, thresholds: Iterable[float] = DEFAULT_THRESHOLDS) -> dict:
    location = _num(step8.get("context_projection_yards"))
    scale = _recent_scale(step8)
    result = {
        "ready": False,
        "reason": "",
        "qb_name": _safe(step8.get("qb_name"), "Unresolved QB1"),
        "location_yards": location,
        "sigma_yards": scale.get("sigma_yards"),
        "recent_games": scale.get("games", 0),
        "distribution": "ZERO-TRUNCATED NORMAL",
        "scale_source": scale.get("basis"),
        "sportsbook_influence": 0.0,
        "monte_carlo_enabled": False,
        "simulation_count": 0,
        "probability_enabled": False,
        "fair_odds_enabled": False,
        "ev_enabled": False,
        "ranking_enabled": False,
        "recommendation_enabled": False,
    }

    if not step8.get("ready"):
        result["reason"] = "Step 8 contextual projection is required"
        return result
    if not (_finite(location) and location >= 0.0):
        result["reason"] = "verified Step 8 contextual central projection is unavailable"
        return result
    if not scale.get("ready"):
        result["reason"] = scale.get("basis") or "verified recent variability is unavailable"
        return result

    sigma = _num(scale.get("sigma_yards"))
    quantiles = {
        "p10": truncated_normal_quantile(0.10, location, sigma),
        "p25": truncated_normal_quantile(0.25, location, sigma),
        "p50": truncated_normal_quantile(0.50, location, sigma),
        "p75": truncated_normal_quantile(0.75, location, sigma),
        "p90": truncated_normal_quantile(0.90, location, sigma),
    }
    threshold_rows = [threshold_probability(value, location, sigma) for value in thresholds]
    threshold_rows = [row for row in threshold_rows if row.get("ready")]
    confidence, confidence_basis = probability_confidence(step8, int(scale.get("games") or 0))

    result.update({
        "ready": True,
        "reason": "",
        "probability_enabled": True,
        "quantiles": quantiles,
        "thresholds": threshold_rows,
        "confidence": confidence,
        "confidence_basis": confidence_basis,
        "model_statement": "analytic zero-truncated normal using Step 8 location and verified recent-game sample SD",
        "sampling_error": 0.0,
    })
    return result


__all__ = [
    "DEFAULT_THRESHOLDS",
    "MIN_RECENT_GAMES",
    "MODEL_VERSION",
    "build_distribution",
    "probability_confidence",
    "threshold_probability",
    "truncated_normal_cdf",
    "truncated_normal_quantile",
]
