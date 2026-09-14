"""NFL Spread Monte Carlo V1 — deterministic market-firewalled margin simulation.

The football model owns the projected scoring-margin distribution. A sportsbook
spread is accepted only after all simulated football margins are generated, and
is used exclusively to grade cover/push outcomes.

Margin convention:
    away_margin = away_points - home_points

Therefore an away spread of -3.0 covers when:
    simulated_away_margin + (-3.0) > 0

The simulator rounds latent Gaussian margin draws to integer NFL scoring margins
before win/cover/push settlement so whole-number spreads can produce real pushes.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np

SIMULATOR_VERSION = "NFL SPREAD MC V1 • DETERMINISTIC 5M"
CERTIFIED_SIMULATIONS = 5_000_000
DEFAULT_SIMULATIONS = CERTIFIED_SIMULATIONS
DEFAULT_BATCH_SIZE = 250_000
DEFAULT_SEED = 20260914
MAX_SIMULATIONS = 10_000_000
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
CERTIFIED_MAX_MC_SE = 0.00025
BASE_BATCH_CONVERGENCE_TOLERANCE = 0.005


def _num(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return math.nan
    return out if math.isfinite(out) else math.nan


def _base_result(
    prediction: dict[str, Any] | None,
    simulations: int,
    seed: int,
    batch_size: int,
    market_away_spread: float | None,
) -> dict[str, Any]:
    pred = prediction or {}
    return {
        "ready": False,
        "simulator_version": SIMULATOR_VERSION,
        "model_version": str(pred.get("model_version") or ""),
        "model_quality": str(pred.get("model_quality") or "LOW"),
        "game_id": str(pred.get("game_id") or ""),
        "simulations": int(simulations),
        "certified_simulations": CERTIFIED_SIMULATIONS,
        "batch_size": int(batch_size),
        "seed": int(seed),
        "market_away_spread": market_away_spread,
        "market_line_role": "settlement_only",
        "sportsbook_projection_influence": 0.0,
        "sportsbook_inputs_to_projection": [],
        "certified_run": False,
        "converged": False,
        "error": "",
    }


def _validate_inputs(
    prediction: dict[str, Any] | None,
    simulations: int,
    seed: int,
    batch_size: int,
    market_away_spread: float | None,
) -> tuple[dict[str, Any], float, float, float | None]:
    result = _base_result(prediction, simulations, seed, batch_size, market_away_spread)
    if not isinstance(prediction, dict) or not prediction.get("ready"):
        result["error"] = str((prediction or {}).get("error") or "margin prediction is not ready")
        return result, math.nan, math.nan, None

    try:
        simulations = int(simulations)
        batch_size = int(batch_size)
        seed = int(seed)
    except (TypeError, ValueError, OverflowError):
        result["error"] = "simulation count, batch size, and seed must be integers"
        return result, math.nan, math.nan, None

    if simulations <= 0 or simulations > MAX_SIMULATIONS:
        result["error"] = f"simulations must be between 1 and {MAX_SIMULATIONS:,}"
        return result, math.nan, math.nan, None
    if batch_size <= 0 or batch_size > simulations:
        result["error"] = "batch_size must be positive and no larger than simulations"
        return result, math.nan, math.nan, None
    if seed < 0:
        result["error"] = "seed must be a non-negative integer"
        return result, math.nan, math.nan, None

    model_influence = _num(prediction.get("sportsbook_projection_influence", 0.0))
    sportsbook_inputs = prediction.get("sportsbook_inputs") or []
    if not math.isfinite(model_influence) or abs(model_influence) > 1e-12 or sportsbook_inputs:
        result["error"] = "sportsbook/model firewall violation detected in margin prediction"
        return result, math.nan, math.nan, None

    mean_margin = _num(prediction.get("projected_away_margin"))
    parameter_se = _num(prediction.get("parameter_se"))
    residual_sd = _num(prediction.get("residual_sd"))
    if not math.isfinite(mean_margin):
        result["error"] = "projected_away_margin is not finite"
        return result, math.nan, math.nan, None
    if not math.isfinite(parameter_se) or parameter_se < 0:
        result["error"] = "parameter_se must be finite and non-negative"
        return result, math.nan, math.nan, None
    if not math.isfinite(residual_sd) or residual_sd <= 0:
        result["error"] = "residual_sd must be finite and positive"
        return result, math.nan, math.nan, None

    predictive_sd = float(math.hypot(parameter_se, residual_sd))
    if not math.isfinite(predictive_sd) or predictive_sd <= 0:
        result["error"] = "combined predictive standard deviation is invalid"
        return result, math.nan, math.nan, None

    spread: float | None = None
    if market_away_spread is not None:
        spread = _num(market_away_spread)
        if not math.isfinite(spread):
            result["error"] = "market_away_spread must be finite when supplied"
            return result, math.nan, math.nan, None

    result.update(
        {
            "simulations": simulations,
            "batch_size": batch_size,
            "seed": seed,
            "market_away_spread": spread,
        }
    )
    return result, mean_margin, predictive_sd, spread


def _probability_se(probability: float, simulations: int) -> float:
    p = min(max(float(probability), 0.0), 1.0)
    return float(math.sqrt(p * (1.0 - p) / max(int(simulations), 1)))


def _distribution(margins: np.ndarray) -> dict[str, float]:
    values, counts = np.unique(margins, return_counts=True)
    total = float(margins.size)
    return {str(int(v)): float(c / total) for v, c in zip(values, counts)}


def simulate_from_prediction(
    prediction: dict[str, Any],
    market_away_spread: float | None = None,
    *,
    simulations: int = DEFAULT_SIMULATIONS,
    seed: int = DEFAULT_SEED,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    """Simulate an NFL away-minus-home margin distribution deterministically.

    `market_away_spread` is settlement context only. It never changes the mean,
    uncertainty, RNG seed, generated margins, or distribution fingerprint.
    """
    result, mean_margin, predictive_sd, spread = _validate_inputs(
        prediction, simulations, seed, batch_size, market_away_spread
    )
    if result.get("error"):
        return result

    simulations = int(result["simulations"])
    batch_size = int(result["batch_size"])
    seed = int(result["seed"])

    rng = np.random.default_rng(seed)
    margins = np.empty(simulations, dtype=np.int16)
    batch_win_rates: list[float] = []
    batch_cover_rates: list[float] = []
    batch_push_rates: list[float] = []

    for start in range(0, simulations, batch_size):
        stop = min(start + batch_size, simulations)
        size = stop - start
        latent = rng.normal(loc=mean_margin, scale=predictive_sd, size=size)
        rounded = np.rint(latent)
        if np.any(rounded < np.iinfo(np.int16).min) or np.any(rounded > np.iinfo(np.int16).max):
            result["error"] = "simulated margin exceeded int16 settlement bounds"
            return result
        batch = rounded.astype(np.int16, copy=False)
        margins[start:stop] = batch

        batch_win_rates.append(float(np.mean(batch > 0)))
        if spread is not None:
            settlement = batch.astype(np.float64) + spread
            batch_cover_rates.append(float(np.mean(settlement > 1e-12)))
            batch_push_rates.append(float(np.mean(np.abs(settlement) <= 1e-12)))

    away_win_probability = float(np.mean(margins > 0))
    tie_probability = float(np.mean(margins == 0))
    home_win_probability = float(np.mean(margins < 0))

    simulated_mean = float(np.mean(margins, dtype=np.float64))
    simulated_median = float(np.median(margins))
    q05, q25, q75, q95 = (
        float(x) for x in np.quantile(margins, [0.05, 0.25, 0.75, 0.95])
    )

    away_win_mc_se = _probability_se(away_win_probability, simulations)
    max_batch_win_diff = max(
        (abs(rate - away_win_probability) for rate in batch_win_rates),
        default=0.0,
    )

    effective_batch_n = min(batch_size, simulations)
    batch_sampling_floor = 4.0 * math.sqrt(0.25 / max(effective_batch_n, 1))
    convergence_tolerance = float(
        max(BASE_BATCH_CONVERGENCE_TOLERANCE, batch_sampling_floor)
    )

    result.update(
        {
            "projected_away_margin": float(mean_margin),
            "projected_home_margin": float(-mean_margin),
            "parameter_se": float(_num(prediction.get("parameter_se"))),
            "residual_sd": float(_num(prediction.get("residual_sd"))),
            "predictive_sd": float(predictive_sd),
            "simulated_away_margin_mean": simulated_mean,
            "simulated_away_margin_median": simulated_median,
            "margin_quantiles": {
                "p05": q05,
                "p25": q25,
                "p50": simulated_median,
                "p75": q75,
                "p95": q95,
            },
            "margin_distribution": _distribution(margins),
            "away_win_probability": away_win_probability,
            "home_win_probability": home_win_probability,
            "tie_probability": tie_probability,
            "away_win_mc_se": away_win_mc_se,
            "max_batch_win_probability_diff": float(max_batch_win_diff),
            "convergence_tolerance": convergence_tolerance,
            "distribution_fingerprint": hashlib.sha256(margins.tobytes()).hexdigest(),
            "batches": int(math.ceil(simulations / batch_size)),
        }
    )

    convergence_components = [max_batch_win_diff <= convergence_tolerance]

    if spread is not None:
        settlement = margins.astype(np.float64) + spread
        away_cover_probability = float(np.mean(settlement > 1e-12))
        push_probability = float(np.mean(np.abs(settlement) <= 1e-12))
        home_cover_probability = float(np.mean(settlement < -1e-12))
        non_push = max(1.0 - push_probability, 0.0)
        conditional_away_cover = (
            float(away_cover_probability / non_push) if non_push > 1e-15 else math.nan
        )

        away_cover_mc_se = _probability_se(away_cover_probability, simulations)
        push_mc_se = _probability_se(push_probability, simulations)
        max_batch_cover_diff = max(
            (abs(rate - away_cover_probability) for rate in batch_cover_rates),
            default=0.0,
        )
        max_batch_push_diff = max(
            (abs(rate - push_probability) for rate in batch_push_rates),
            default=0.0,
        )
        result.update(
            {
                "away_cover_probability": away_cover_probability,
                "home_cover_probability": home_cover_probability,
                "push_probability": push_probability,
                "away_cover_probability_non_push": conditional_away_cover,
                "away_cover_mc_se": away_cover_mc_se,
                "push_mc_se": push_mc_se,
                "max_batch_cover_probability_diff": float(max_batch_cover_diff),
                "max_batch_push_probability_diff": float(max_batch_push_diff),
            }
        )
        convergence_components.extend(
            [
                max_batch_cover_diff <= convergence_tolerance,
                max_batch_push_diff <= convergence_tolerance,
            ]
        )

    converged = bool(all(convergence_components))
    full_5m = simulations == CERTIFIED_SIMULATIONS
    se_ok = away_win_mc_se <= CERTIFIED_MAX_MC_SE
    if spread is not None:
        se_ok = bool(
            se_ok
            and result["away_cover_mc_se"] <= CERTIFIED_MAX_MC_SE
            and result["push_mc_se"] <= CERTIFIED_MAX_MC_SE
        )

    result.update(
        {
            "ready": True,
            "converged": converged,
            "certified_run": bool(full_5m and converged and se_ok),
            "certification": {
                "required_simulations": CERTIFIED_SIMULATIONS,
                "full_5m": full_5m,
                "mc_se_within_limit": bool(se_ok),
                "batch_stability_pass": converged,
                "sportsbook_firewall_pass": True,
            },
            "error": "",
        }
    )
    return result


def simulate_game_spread(
    game: dict[str, Any],
    day_str: str,
    market_away_spread: float | None = None,
    *,
    fitted: dict[str, Any] | None = None,
    simulations: int = DEFAULT_SIMULATIONS,
    seed: int = DEFAULT_SEED,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    """Predict with Spread Model V1, then simulate without market feedback."""
    from nfl_spread_model_v1 import predict_game_margin

    prediction = predict_game_margin(game, day_str, fitted=fitted)
    return simulate_from_prediction(
        prediction,
        market_away_spread,
        simulations=simulations,
        seed=seed,
        batch_size=batch_size,
    )


__all__ = [
    "BASE_BATCH_CONVERGENCE_TOLERANCE",
    "CERTIFIED_MAX_MC_SE",
    "CERTIFIED_SIMULATIONS",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_SEED",
    "DEFAULT_SIMULATIONS",
    "MAX_SIMULATIONS",
    "SIMULATOR_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "simulate_from_prediction",
    "simulate_game_spread",
]
