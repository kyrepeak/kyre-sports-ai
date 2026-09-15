"""NFL Game Totals O/U Probability + Monte Carlo V1.

The distribution is generated entirely from the certified football-only Step-9
team-point projection. A sportsbook total may be supplied only after simulated
scores exist, as an evaluation threshold for Over/Under/Push probabilities. It
cannot alter projected means, uncertainty, random draws, or distribution shape.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np

MODEL_VERSION = "NFL GAME TOTALS PROBABILITY V1 • DETERMINISTIC MONTE CARLO"
CERTIFIED_SIMULATIONS = 5_000_000
CERTIFIED_BATCHES = 20
CERTIFIED_SEED = 20_260_915
TEAM_SCORE_DISPERSION = 1.70
MIN_TEAM_SCORE_SIGMA = 6.5
MAX_TEAM_SCORE_SIGMA = 13.5
TEAM_SCORE_CORRELATION = 0.10
MAX_TEAM_SCORE = 80
MAX_TOTAL_SCORE = 2 * MAX_TEAM_SCORE
SPORTSBOOK_DISTRIBUTION_INFLUENCE = 0.0
CONVERGENCE_MAX_SE = 0.001
CONVERGENCE_MAX_BATCH_DIFF = 0.01


class NFLGameTotalsProbabilityError(RuntimeError):
    """The Game Totals probability contract could not be proven safely."""


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise NFLGameTotalsProbabilityError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise NFLGameTotalsProbabilityError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise NFLGameTotalsProbabilityError(f"{field} must be finite")
    return number


def _validate_projection(projection: Mapping[str, Any]) -> tuple[str, str, str, float, float, float]:
    if not isinstance(projection, Mapping):
        raise NFLGameTotalsProbabilityError("projection must be an object")
    if projection.get("ready") is not True:
        raise NFLGameTotalsProbabilityError("projection is not ready")
    if not _text(projection.get("model_version")).startswith("NFL GAME TOTALS PROJECTION V1"):
        raise NFLGameTotalsProbabilityError("projection model contract mismatch")
    if projection.get("football_only") is not True:
        raise NFLGameTotalsProbabilityError("projection is not certified football-only")
    if projection.get("sportsbook_projection_influence") != 0.0:
        raise NFLGameTotalsProbabilityError("sportsbook projection influence must remain exactly 0.0")
    if projection.get("sportsbook_inputs") not in ([], (), None):
        raise NFLGameTotalsProbabilityError("sportsbook inputs are forbidden in the projection distribution")
    if projection.get("market_total_used") is not False:
        raise NFLGameTotalsProbabilityError("projection must not use a market total")

    event_id = _text(projection.get("official_event_id"))
    away_id = _text(projection.get("away_team_id"))
    home_id = _text(projection.get("home_team_id"))
    if not event_id.isdigit():
        raise NFLGameTotalsProbabilityError("official event ID must be numeric")
    if not away_id.isdigit() or not home_id.isdigit() or away_id == home_id:
        raise NFLGameTotalsProbabilityError("official team identities are invalid")

    away_mean = _finite(projection.get("projected_away_points"), "projected_away_points")
    home_mean = _finite(projection.get("projected_home_points"), "projected_home_points")
    projected_total = _finite(projection.get("projected_total"), "projected_total")
    if away_mean < 0.0 or home_mean < 0.0 or away_mean > 80.0 or home_mean > 80.0:
        raise NFLGameTotalsProbabilityError("projected team points are outside the supported NFL range")
    if not math.isclose(away_mean + home_mean, projected_total, abs_tol=1e-9):
        raise NFLGameTotalsProbabilityError("projected total does not equal projected team points")
    return event_id, away_id, home_id, away_mean, home_mean, projected_total


def _validate_run_shape(total_line: Any, simulations: Any, batches: Any, seed: Any) -> tuple[float, int, int, int]:
    line = _finite(total_line, "total_line")
    if line < 0.0 or line > float(MAX_TOTAL_SCORE):
        raise NFLGameTotalsProbabilityError("total_line is outside the supported NFL range")
    if isinstance(simulations, bool) or isinstance(batches, bool) or isinstance(seed, bool):
        raise NFLGameTotalsProbabilityError("simulation controls must be integers")
    try:
        n = int(simulations)
        batch_count = int(batches)
        random_seed = int(seed)
    except (TypeError, ValueError) as exc:
        raise NFLGameTotalsProbabilityError("simulation controls must be integers") from exc
    if n < 10_000 or n > 20_000_000:
        raise NFLGameTotalsProbabilityError("simulations must be between 10,000 and 20,000,000")
    if batch_count < 1 or batch_count > 100 or n % batch_count != 0:
        raise NFLGameTotalsProbabilityError("simulations must divide evenly across 1..100 batches")
    if random_seed < 0:
        raise NFLGameTotalsProbabilityError("seed must be non-negative")
    return line, n, batch_count, random_seed


def _team_sigma(mean_points: float) -> float:
    raw = TEAM_SCORE_DISPERSION * math.sqrt(max(mean_points, 1.0))
    return min(MAX_TEAM_SCORE_SIGMA, max(MIN_TEAM_SCORE_SIGMA, raw))


def _american_from_probability(probability: float) -> int:
    if not 0.0 < probability < 1.0:
        raise NFLGameTotalsProbabilityError("fair probability must be strictly between 0 and 1")
    if probability >= 0.5:
        return int(round(-100.0 * probability / (1.0 - probability)))
    return int(round(100.0 * (1.0 - probability) / probability))


def _histogram_quantile(histogram: np.ndarray, probability: float, total_count: int) -> int:
    if total_count <= 0:
        raise NFLGameTotalsProbabilityError("simulation histogram is empty")
    target = max(1, int(math.ceil(float(probability) * total_count)))
    cumulative = np.cumsum(histogram, dtype=np.int64)
    return int(np.searchsorted(cumulative, target, side="left"))


def simulate_over_under(
    projection: Mapping[str, Any],
    total_line: float,
    *,
    simulations: int = CERTIFIED_SIMULATIONS,
    batches: int = CERTIFIED_BATCHES,
    seed: int = CERTIFIED_SEED,
) -> dict[str, Any]:
    """Simulate integer NFL scores, then evaluate a total line as threshold-only context."""
    event_id, away_id, home_id, away_mean, home_mean, projected_total = _validate_projection(projection)
    line, n, batch_count, random_seed = _validate_run_shape(total_line, simulations, batches, seed)

    away_sigma = _team_sigma(away_mean)
    home_sigma = _team_sigma(home_mean)
    shared_scale = math.sqrt(TEAM_SCORE_CORRELATION)
    independent_scale = math.sqrt(1.0 - TEAM_SCORE_CORRELATION)
    rng = np.random.default_rng(random_seed)
    batch_size = n // batch_count

    over_count = 0
    under_count = 0
    push_count = 0
    total_sum = 0
    histogram = np.zeros(MAX_TOTAL_SCORE + 1, dtype=np.int64)
    batch_over_probabilities: list[float] = []

    for _ in range(batch_count):
        shared = rng.standard_normal(batch_size)
        away_noise = rng.standard_normal(batch_size)
        home_noise = rng.standard_normal(batch_size)

        away_z = shared_scale * shared + independent_scale * away_noise
        home_z = shared_scale * shared + independent_scale * home_noise
        away_scores = np.rint(np.clip(away_mean + away_sigma * away_z, 0.0, MAX_TEAM_SCORE)).astype(np.int16)
        home_scores = np.rint(np.clip(home_mean + home_sigma * home_z, 0.0, MAX_TEAM_SCORE)).astype(np.int16)
        totals = (away_scores + home_scores).astype(np.int16)

        batch_over = int(np.count_nonzero(totals > line))
        batch_under = int(np.count_nonzero(totals < line))
        batch_push = batch_size - batch_over - batch_under
        over_count += batch_over
        under_count += batch_under
        push_count += batch_push
        total_sum += int(totals.sum(dtype=np.int64))
        histogram += np.bincount(totals, minlength=MAX_TOTAL_SCORE + 1)[: MAX_TOTAL_SCORE + 1]
        batch_over_probabilities.append(batch_over / batch_size)

    over_probability = over_count / n
    under_probability = under_count / n
    push_probability = push_count / n
    probability_sum = over_probability + under_probability + push_probability
    if not math.isclose(probability_sum, 1.0, abs_tol=1e-12):
        raise NFLGameTotalsProbabilityError("simulation probabilities do not sum to 1")

    non_push = over_count + under_count
    if non_push <= 0:
        raise NFLGameTotalsProbabilityError("simulation produced no resolvable Over/Under outcomes")
    over_no_push = over_count / non_push
    under_no_push = under_count / non_push

    monte_carlo_se = math.sqrt(max(0.0, over_probability * (1.0 - over_probability)) / n)
    max_batch_diff = max(abs(value - over_probability) for value in batch_over_probabilities)
    converged = monte_carlo_se < CONVERGENCE_MAX_SE and max_batch_diff < CONVERGENCE_MAX_BATCH_DIFF

    simulated_mean = total_sum / n
    median = _histogram_quantile(histogram, 0.50, n)
    p10 = _histogram_quantile(histogram, 0.10, n)
    p90 = _histogram_quantile(histogram, 0.90, n)
    theoretical_total_sigma = math.sqrt(
        away_sigma * away_sigma
        + home_sigma * home_sigma
        + 2.0 * TEAM_SCORE_CORRELATION * away_sigma * home_sigma
    )

    return {
        "ready": True,
        "model_version": MODEL_VERSION,
        "official_event_id": event_id,
        "away_team_id": away_id,
        "home_team_id": home_id,
        "projected_away_points": away_mean,
        "projected_home_points": home_mean,
        "projected_total": projected_total,
        "market_total_line": line,
        "market_line_role": "evaluation_threshold_only",
        "market_line_influence_on_distribution": SPORTSBOOK_DISTRIBUTION_INFLUENCE,
        "simulated_mean": float(simulated_mean),
        "median": median,
        "p10": p10,
        "p90": p90,
        "over_probability": float(over_probability),
        "under_probability": float(under_probability),
        "push_probability": float(push_probability),
        "fair_odds": {
            "over_no_push_probability": float(over_no_push),
            "under_no_push_probability": float(under_no_push),
            "over_american": _american_from_probability(over_no_push),
            "under_american": _american_from_probability(under_no_push),
        },
        "uncertainty": {
            "away_score_sigma": float(away_sigma),
            "home_score_sigma": float(home_sigma),
            "team_score_correlation": TEAM_SCORE_CORRELATION,
            "theoretical_total_sigma": float(theoretical_total_sigma),
            "team_score_dispersion": TEAM_SCORE_DISPERSION,
        },
        "simulation": {
            "simulations": n,
            "batches": batch_count,
            "batch_size": batch_size,
            "seed": random_seed,
            "monte_carlo_se": float(monte_carlo_se),
            "max_batch_over_probability_difference": float(max_batch_diff),
            "converged": bool(converged),
        },
        "football_only_distribution": True,
        "sportsbook_projection_influence": 0.0,
        "sportsbook_distribution_influence": SPORTSBOOK_DISTRIBUTION_INFLUENCE,
        "probability_generated": True,
        "monte_carlo_generated": True,
    }


__all__ = [
    "CERTIFIED_BATCHES",
    "CERTIFIED_SEED",
    "CERTIFIED_SIMULATIONS",
    "MODEL_VERSION",
    "NFLGameTotalsProbabilityError",
    "SPORTSBOOK_DISTRIBUTION_INFLUENCE",
    "TEAM_SCORE_CORRELATION",
    "TEAM_SCORE_DISPERSION",
    "simulate_over_under",
]
