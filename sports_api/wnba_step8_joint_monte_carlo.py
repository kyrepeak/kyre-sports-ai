"""Step 8D WNBA joint P/R/A Monte Carlo probability engine.

This layer converts the certified Step-8C deterministic target mean into a
reproducible joint discrete probability distribution without assuming points,
rebounds, and assists are independent.

The five exact official recent box-score rows are the only dispersion/dependence
evidence used in v1. Because five games are a very small covariance sample,
variance-to-mean ratios are shrunk toward a Poisson reference and the empirical
P/R/A correlation matrix is shrunk toward identity before simulation. A Gaussian
copula then couples discrete Poisson / negative-binomial / binomial marginals.

Production, scheduler, sportsbook, Supabase, and persistence paths remain OFF.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from typing import Any, Mapping

import numpy as np

from sports_api.wnba_step8_context_adjustment import (
    MODEL_VERSION as STEP8C_MODEL_VERSION,
    SCHEMA_VERSION as STEP8C_SCHEMA_VERSION,
    build_step8_context_adjusted_projection,
)
from sports_api.wnba_step8_official_box_baseline import build_step8_official_box_baseline
from sports_api.wnba_step8_projection_handoff import get_player_game_step8_projection_handoff

SOURCE = "Kyre Sports API WNBA Step 8D regularized joint Monte Carlo"
SCHEMA_VERSION = "wnba_step_8d_joint_probability_distribution_v1"
MODEL_VERSION = "wnba_step8d_regularized_gaussian_copula_counts_2026_regular_v1"
STEP8_MONTE_CARLO_ENABLED_ENV = "WNBA_STEP8_MONTE_CARLO_ENABLED"
DEFAULT_SIMULATIONS = 5_000_000
DEFAULT_BATCH_SIZE = 250_000
MIN_SIMULATIONS = 10_000
REGULARIZATION_PRIOR_GAMES = 15.0
CDF_TAIL_EPSILON = 1e-12
MAX_MARGINAL_COUNT = 512
CERTIFIED_MAX_BATCH_PROBABILITY_RANGE = 0.01
CERTIFIED_MAX_MEAN_TARGET_ERROR = 0.05
CERTIFIED_MAX_MONTE_CARLO_SE = 0.0005
_STATS = ("points", "rebounds", "assists")
_PRA = "points_rebounds_assists"
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep8MonteCarloDisabledError(RuntimeError):
    """Raised when the isolated Step-8D engine is not explicitly enabled."""


class WNBAStep8MonteCarloUpstreamError(RuntimeError):
    """Raised when certified Step-8 evidence is malformed or contradictory."""


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def step8_monte_carlo_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP8_MONTE_CARLO_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [key for key in _OFF_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise WNBAStep8MonteCarloDisabledError(
            "Step 8D refuses production switches: " + ", ".join(bad)
        )
    for key in (
        "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED",
        "WNBA_STEP8_CORE_PROJECTION_ENABLED",
        "WNBA_STEP8_CONTEXT_ADJUSTMENT_ENABLED",
        STEP8_MONTE_CARLO_ENABLED_ENV,
    ):
        if not _truthy(source.get(key)):
            raise WNBAStep8MonteCarloDisabledError(
                f"Step 8D requires isolated flag {key}=true."
            )


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise WNBAStep8MonteCarloUpstreamError(f"Step 8D {label} must be numeric.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep8MonteCarloUpstreamError(
            f"Step 8D {label} must be numeric."
        ) from exc
    if not math.isfinite(result):
        raise WNBAStep8MonteCarloUpstreamError(f"Step 8D {label} must be finite.")
    return result


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _regularization_weight(game_count: int) -> float:
    if game_count <= 0:
        raise WNBAStep8MonteCarloUpstreamError("Step 8D requires at least one historical game.")
    return float(game_count / (game_count + REGULARIZATION_PRIOR_GAMES))


def _validate_inputs(
    adjusted: Mapping[str, Any], baseline: Mapping[str, Any]
) -> tuple[str, int, dict[str, float], np.ndarray]:
    if not isinstance(adjusted, Mapping) or not isinstance(baseline, Mapping):
        raise WNBAStep8MonteCarloUpstreamError("Step 8D requires Step-8C and official-box mappings.")
    if adjusted.get("data_type") != "context_adjusted_deterministic_player_projection":
        raise WNBAStep8MonteCarloUpstreamError("Step 8D received the wrong Step-8C data type.")
    if adjusted.get("schema_version") != STEP8C_SCHEMA_VERSION or adjusted.get("model_version") != STEP8C_MODEL_VERSION:
        raise WNBAStep8MonteCarloUpstreamError("Step 8D received an unsupported Step-8C contract.")
    if baseline.get("data_type") != "official_recent_player_box_stat_baseline":
        raise WNBAStep8MonteCarloUpstreamError("Step 8D received the wrong official-box baseline type.")

    game_id = str(adjusted.get("game_id") or "").strip()
    try:
        player_id = int(adjusted.get("player_id"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep8MonteCarloUpstreamError("Step 8D player ID is invalid.") from exc
    if not game_id or player_id <= 0:
        raise WNBAStep8MonteCarloUpstreamError("Step 8D game/player identity is invalid.")
    if str(baseline.get("requested_game_id") or "").strip() != game_id or baseline.get("player_id") != player_id:
        raise WNBAStep8MonteCarloUpstreamError("Step 8D baseline identity disagrees with Step 8C.")

    projection = adjusted.get("projection")
    if not isinstance(projection, Mapping):
        raise WNBAStep8MonteCarloUpstreamError("Step 8D Step-8C target projection is missing.")
    target = {stat: _number(projection.get(stat), f"target {stat}") for stat in _STATS}
    target[_PRA] = _number(projection.get(_PRA), "target PRA")
    if any(target[stat] <= 0.0 for stat in _STATS):
        raise WNBAStep8MonteCarloUpstreamError("Step 8D target P/R/A means must be positive.")
    if abs(sum(target[stat] for stat in _STATS) - target[_PRA]) > 2e-5:
        raise WNBAStep8MonteCarloUpstreamError("Step 8D target PRA does not equal P+R+A.")
    if target["points"] > 100.0 or target["rebounds"] > 60.0 or target["assists"] > 40.0:
        raise WNBAStep8MonteCarloUpstreamError("Step 8D target mean is outside certified WNBA plausibility bounds.")

    games = baseline.get("games")
    if not isinstance(games, list) or len(games) != 5:
        raise WNBAStep8MonteCarloUpstreamError("Step 8D requires exactly five official recent box rows.")
    rows: list[list[float]] = []
    for row in games:
        if not isinstance(row, Mapping):
            raise WNBAStep8MonteCarloUpstreamError("Step 8D found a malformed official box row.")
        values = []
        for stat in _STATS:
            value = _number(row.get(stat), f"official game {stat}")
            if value < 0 or abs(value - round(value)) > 1e-9:
                raise WNBAStep8MonteCarloUpstreamError(
                    f"Step 8D official {stat} must be a nonnegative integer count."
                )
            values.append(value)
        pra = _number(row.get(_PRA), "official game PRA")
        if abs(sum(values) - pra) > 1e-9:
            raise WNBAStep8MonteCarloUpstreamError("Step 8D official row PRA is inconsistent.")
        rows.append(values)
    matrix = np.asarray(rows, dtype=np.float64)
    if matrix.shape != (5, 3):
        raise WNBAStep8MonteCarloUpstreamError("Step 8D official matrix has the wrong shape.")
    return game_id, player_id, target, matrix


def _marginal_spec(mean_target: float, historical: np.ndarray, weight: float) -> dict[str, Any]:
    historical_mean = float(np.mean(historical))
    historical_variance = float(np.var(historical))
    if historical_mean <= 0.0:
        raise WNBAStep8MonteCarloUpstreamError("Step 8D cannot calibrate dispersion from a zero historical mean.")
    empirical_vtm = historical_variance / historical_mean
    regularized_vtm = 1.0 + weight * (empirical_vtm - 1.0)
    if not 0.5 <= regularized_vtm <= 3.0:
        raise WNBAStep8MonteCarloUpstreamError(
            "Step 8D regularized variance-to-mean ratio is outside certified bounds."
        )
    target_variance = mean_target * regularized_vtm
    tolerance = max(1e-10, 0.005 * mean_target)

    if abs(target_variance - mean_target) <= tolerance:
        family = "poisson"
        params = {"mean": mean_target}
        actual_variance = mean_target
    elif target_variance > mean_target:
        size = mean_target * mean_target / (target_variance - mean_target)
        probability = size / (size + mean_target)
        family = "negative_binomial"
        params = {"size": size, "success_probability": probability}
        actual_variance = mean_target + mean_target * mean_target / size
    else:
        denominator = mean_target - target_variance
        trials = int(math.ceil(mean_target * mean_target / denominator))
        trials = max(trials, int(math.ceil(mean_target)))
        probability = mean_target / trials
        family = "binomial"
        params = {"trials": trials, "success_probability": probability}
        actual_variance = mean_target * (1.0 - probability)

    return {
        "family": family,
        "mean": mean_target,
        "variance": actual_variance,
        "stddev": math.sqrt(actual_variance),
        "historical_mean": historical_mean,
        "historical_population_variance": historical_variance,
        "historical_variance_to_mean": empirical_vtm,
        "regularized_variance_to_mean": actual_variance / mean_target,
        "parameters": params,
    }


def _build_model_spec(target: Mapping[str, float], matrix: np.ndarray) -> dict[str, Any]:
    game_count = int(matrix.shape[0])
    weight = _regularization_weight(game_count)
    marginals = {
        stat: _marginal_spec(float(target[stat]), matrix[:, index], weight)
        for index, stat in enumerate(_STATS)
    }
    empirical_corr = np.corrcoef(matrix, rowvar=False)
    if empirical_corr.shape != (3, 3) or not np.all(np.isfinite(empirical_corr)):
        raise WNBAStep8MonteCarloUpstreamError("Step 8D empirical correlation matrix is not finite.")
    regularized_corr = (1.0 - weight) * np.eye(3, dtype=np.float64) + weight * empirical_corr
    regularized_corr = (regularized_corr + regularized_corr.T) / 2.0
    eigenvalues = np.linalg.eigvalsh(regularized_corr)
    if float(np.min(eigenvalues)) <= 1e-9:
        raise WNBAStep8MonteCarloUpstreamError("Step 8D regularized correlation matrix is not positive definite.")

    return {
        "sample_game_count": game_count,
        "regularization_prior_games": REGULARIZATION_PRIOR_GAMES,
        "empirical_evidence_weight": weight,
        "marginals": marginals,
        "empirical_correlation": empirical_corr,
        "regularized_latent_correlation": regularized_corr,
        "regularized_correlation_eigenvalues": eigenvalues,
    }


def _cdf_table(spec: Mapping[str, Any]) -> np.ndarray:
    family = spec["family"]
    mean_target = float(spec["mean"])
    params = spec["parameters"]
    pmf: list[float] = []

    if family == "poisson":
        value = math.exp(-mean_target)
        pmf.append(value)
        for k in range(MAX_MARGINAL_COUNT):
            if sum(pmf) >= 1.0 - CDF_TAIL_EPSILON:
                break
            value = value * mean_target / (k + 1)
            pmf.append(value)
    elif family == "negative_binomial":
        size = float(params["size"])
        probability = float(params["success_probability"])
        value = math.exp(size * math.log(probability))
        pmf.append(value)
        for k in range(MAX_MARGINAL_COUNT):
            if sum(pmf) >= 1.0 - CDF_TAIL_EPSILON:
                break
            value = value * ((k + size) / (k + 1.0)) * (1.0 - probability)
            pmf.append(value)
    elif family == "binomial":
        trials = int(params["trials"])
        probability = float(params["success_probability"])
        if probability >= 1.0:
            result = np.zeros(trials + 1, dtype=np.float64)
            result[-1] = 1.0
            return np.cumsum(result)
        value = (1.0 - probability) ** trials
        pmf.append(value)
        odds = probability / (1.0 - probability)
        for k in range(trials):
            value = value * ((trials - k) / (k + 1.0)) * odds
            pmf.append(value)
    else:
        raise WNBAStep8MonteCarloUpstreamError(f"Step 8D unsupported marginal family {family!r}.")

    probs = np.asarray(pmf, dtype=np.float64)
    total = float(np.sum(probs))
    if not math.isfinite(total) or total < 1.0 - 1e-9:
        raise WNBAStep8MonteCarloUpstreamError("Step 8D marginal CDF truncation lost too much probability mass.")
    probs /= total
    cdf = np.cumsum(probs)
    cdf[-1] = 1.0
    return cdf


def _standard_normal_cdf(values: np.ndarray) -> np.ndarray:
    """Fast vectorized normal CDF approximation; max absolute error ~7.5e-8."""
    x = np.asarray(values, dtype=np.float64)
    absolute = np.abs(x)
    t = 1.0 / (1.0 + 0.2316419 * absolute)
    poly = t * (
        0.319381530
        + t * (
            -0.356563782
            + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))
        )
    )
    density = 0.3989422804014327 * np.exp(-0.5 * absolute * absolute)
    upper = 1.0 - density * poly
    result = np.where(x >= 0.0, upper, 1.0 - upper)
    return np.clip(result, 0.0, 1.0)


def _seed_from_inputs(adjusted: Mapping[str, Any], baseline: Mapping[str, Any]) -> int:
    material = "|".join(
        (
            MODEL_VERSION,
            str(adjusted.get("projection_content_sha256") or ""),
            str(baseline.get("baseline_content_sha256") or ""),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _hist_summary(hist: np.ndarray, simulations: int) -> dict[str, Any]:
    probabilities = hist.astype(np.float64) / float(simulations)
    values = np.arange(probabilities.size, dtype=np.float64)
    expected = float(np.dot(values, probabilities))
    variance = float(np.dot((values - expected) ** 2, probabilities))
    cdf = np.cumsum(probabilities)

    def quantile(q: float) -> int:
        return int(np.searchsorted(cdf, q, side="left"))

    pmf = [
        {"value": int(index), "probability": round(float(probability), 10)}
        for index, probability in enumerate(probabilities)
        if probability > 0.0
    ]
    return {
        "expected": round(expected, 8),
        "variance": round(variance, 8),
        "stddev": round(math.sqrt(max(variance, 0.0)), 8),
        "median": quantile(0.5),
        "mode": int(np.argmax(probabilities)),
        "quantiles": {
            "p10": quantile(0.10),
            "p25": quantile(0.25),
            "p50": quantile(0.50),
            "p75": quantile(0.75),
            "p90": quantile(0.90),
            "p95": quantile(0.95),
        },
        "probability_mass": pmf,
        "probability_mass_sum": round(float(np.sum(probabilities)), 12),
    }


def _line_probability_from_hist(hist: np.ndarray, simulations: int, line: float) -> dict[str, Any]:
    if not math.isfinite(float(line)):
        raise ValueError("line must be finite")
    total = float(simulations)
    indices = np.arange(hist.size)
    if float(line).is_integer():
        integer = int(line)
        under = float(hist[indices < integer].sum()) / total
        push = float(hist[indices == integer].sum()) / total
        over = float(hist[indices > integer].sum()) / total
    else:
        under = float(hist[indices < line].sum()) / total
        push = 0.0
        over = float(hist[indices > line].sum()) / total
    return {
        "line": float(line),
        "under_probability": round(under, 10),
        "push_probability": round(push, 10),
        "over_probability": round(over, 10),
    }


def simulate_step8_joint_distribution(
    adjusted: Mapping[str, Any],
    baseline: Mapping[str, Any],
    *,
    simulations: int = DEFAULT_SIMULATIONS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    seed: int | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Create the isolated Step-8D joint discrete probability distribution."""
    _assert_safe_environment(env)
    if simulations < MIN_SIMULATIONS:
        raise ValueError(f"Step 8D requires at least {MIN_SIMULATIONS:,} simulations.")
    if batch_size <= 0 or batch_size > simulations:
        raise ValueError("Step 8D batch_size must be positive and no larger than simulations.")

    game_id, player_id, target, history = _validate_inputs(adjusted, baseline)
    spec = _build_model_spec(target, history)
    latent_corr = spec["regularized_latent_correlation"]
    cholesky = np.linalg.cholesky(latent_corr)
    cdf_tables = [_cdf_table(spec["marginals"][stat]) for stat in _STATS]

    actual_seed = int(_seed_from_inputs(adjusted, baseline) if seed is None else seed)
    rng = np.random.default_rng(actual_seed)
    histograms: dict[str, np.ndarray] = {stat: np.zeros(1, dtype=np.int64) for stat in (*_STATS, _PRA)}
    stat_sums = np.zeros(3, dtype=np.float64)
    cross_sums = np.zeros((3, 3), dtype=np.float64)
    probe_thresholds = np.asarray([math.ceil(target[stat]) for stat in _STATS], dtype=np.int64)
    pra_probe_threshold = int(math.ceil(target[_PRA]))
    batch_probe_probabilities: list[list[float]] = []
    batch_means: list[list[float]] = []
    batch_sizes: list[int] = []

    remaining = int(simulations)
    while remaining > 0:
        current = min(int(batch_size), remaining)
        normals = rng.standard_normal((current, 3)) @ cholesky.T
        uniforms = _standard_normal_cdf(normals)
        counts = np.empty((current, 3), dtype=np.int16)
        for index, cdf in enumerate(cdf_tables):
            counts[:, index] = np.searchsorted(cdf, uniforms[:, index], side="left").astype(np.int16)
        pra = counts.sum(axis=1, dtype=np.int32)

        for index, stat in enumerate(_STATS):
            local = np.bincount(counts[:, index].astype(np.int64))
            if local.size > histograms[stat].size:
                histograms[stat] = np.pad(histograms[stat], (0, local.size - histograms[stat].size))
            histograms[stat][: local.size] += local
        local_pra = np.bincount(pra.astype(np.int64))
        if local_pra.size > histograms[_PRA].size:
            histograms[_PRA] = np.pad(histograms[_PRA], (0, local_pra.size - histograms[_PRA].size))
        histograms[_PRA][: local_pra.size] += local_pra

        as_float = counts.astype(np.float64)
        stat_sums += np.sum(as_float, axis=0)
        cross_sums += as_float.T @ as_float
        probes = [float(np.mean(counts[:, i] >= probe_thresholds[i])) for i in range(3)]
        probes.append(float(np.mean(pra >= pra_probe_threshold)))
        batch_probe_probabilities.append(probes)
        component_means = np.mean(as_float, axis=0)
        batch_means.append([
            float(component_means[0]),
            float(component_means[1]),
            float(component_means[2]),
            float(np.mean(pra)),
        ])
        batch_sizes.append(current)
        remaining -= current

    distributions = {stat: _hist_summary(histograms[stat], simulations) for stat in (*_STATS, _PRA)}
    achieved_means = stat_sums / float(simulations)
    achieved_covariance = cross_sums / float(simulations) - np.outer(achieved_means, achieved_means)
    achieved_std = np.sqrt(np.maximum(np.diag(achieved_covariance), 0.0))
    denominator = np.outer(achieved_std, achieved_std)
    achieved_corr = np.divide(
        achieved_covariance,
        denominator,
        out=np.eye(3, dtype=np.float64),
        where=denominator > 0.0,
    )
    np.fill_diagonal(achieved_corr, 1.0)

    batch_array = np.asarray(batch_probe_probabilities, dtype=np.float64)
    probe_names = (*_STATS, _PRA)
    probe_probabilities: dict[str, float] = {}
    probe_standard_errors: dict[str, float] = {}
    batch_ranges: dict[str, float] = {}
    for index, stat in enumerate(probe_names):
        threshold = int(probe_thresholds[index]) if index < 3 else pra_probe_threshold
        hist = histograms[stat]
        probability = float(hist[np.arange(hist.size) >= threshold].sum()) / float(simulations)
        probe_probabilities[stat] = probability
        probe_standard_errors[stat] = math.sqrt(max(probability * (1.0 - probability), 0.0) / simulations)
        batch_ranges[stat] = float(np.max(batch_array[:, index]) - np.min(batch_array[:, index]))

    mean_target_errors = {
        stat: abs(distributions[stat]["expected"] - target[stat]) for stat in (*_STATS, _PRA)
    }
    max_batch_range = max(batch_ranges.values())
    max_mean_error = max(mean_target_errors.values())
    max_mc_se = max(probe_standard_errors.values())
    converged = bool(
        simulations >= DEFAULT_SIMULATIONS
        and max_batch_range <= CERTIFIED_MAX_BATCH_PROBABILITY_RANGE
        and max_mean_error <= CERTIFIED_MAX_MEAN_TARGET_ERROR
        and max_mc_se <= CERTIFIED_MAX_MONTE_CARLO_SE
    )

    line_examples = {
        stat: _line_probability_from_hist(
            histograms[stat], simulations, math.floor(target[stat]) + 0.5
        )
        for stat in (*_STATS, _PRA)
    }
    result = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "game_id": game_id,
        "player_id": player_id,
        "team_key": adjusted.get("team_key"),
        "opponent_team_key": adjusted.get("opponent_team_key"),
        "step8c_target": {
            "projection_id": adjusted.get("projection_id"),
            "projection_content_sha256": adjusted.get("projection_content_sha256"),
            **{stat: round(float(target[stat]), 8) for stat in (*_STATS, _PRA)},
        },
        "model_specification": {
            "family": "regularized_gaussian_copula_discrete_counts",
            "dependence_assumption": "P/R/A are jointly simulated and are not assumed independent",
            "sample_game_count": spec["sample_game_count"],
            "regularization_prior_games": spec["regularization_prior_games"],
            "empirical_evidence_weight": round(float(spec["empirical_evidence_weight"]), 8),
            "variance_reference": "Poisson variance-to-mean ratio 1.0",
            "marginals": {
                stat: {
                    key: (
                        round(float(value), 8)
                        if isinstance(value, (float, np.floating))
                        else value
                    )
                    for key, value in spec["marginals"][stat].items()
                }
                for stat in _STATS
            },
            "empirical_correlation": {
                left: {
                    right: round(float(spec["empirical_correlation"][i, j]), 8)
                    for j, right in enumerate(_STATS)
                }
                for i, left in enumerate(_STATS)
            },
            "regularized_latent_correlation": {
                left: {
                    right: round(float(spec["regularized_latent_correlation"][i, j]), 8)
                    for j, right in enumerate(_STATS)
                }
                for i, left in enumerate(_STATS)
            },
            "regularized_correlation_eigenvalues": [
                round(float(value), 8) for value in spec["regularized_correlation_eigenvalues"]
            ],
        },
        "simulation": {
            "simulations": int(simulations),
            "batch_size": int(batch_size),
            "batch_count": len(batch_sizes),
            "batch_sizes": batch_sizes,
            "random_seed": actual_seed,
            "rng": "numpy.default_rng(PCG64)",
            "normal_cdf": "Abramowitz-Stegun vector approximation",
            "marginal_inverse_cdf_tail_epsilon": CDF_TAIL_EPSILON,
        },
        "distributions": distributions,
        "example_half_point_lines_near_target": line_examples,
        "achieved_joint_dependence": {
            "correlation": {
                left: {
                    right: round(float(achieved_corr[i, j]), 8)
                    for j, right in enumerate(_STATS)
                }
                for i, left in enumerate(_STATS)
            }
        },
        "convergence": {
            "probe_thresholds_at_least": {
                "points": int(probe_thresholds[0]),
                "rebounds": int(probe_thresholds[1]),
                "assists": int(probe_thresholds[2]),
                _PRA: pra_probe_threshold,
            },
            "probe_probabilities": {k: round(v, 10) for k, v in probe_probabilities.items()},
            "probe_monte_carlo_standard_errors": {
                k: round(v, 10) for k, v in probe_standard_errors.items()
            },
            "probe_batch_probability_ranges": {k: round(v, 10) for k, v in batch_ranges.items()},
            "mean_target_absolute_errors": {k: round(float(v), 10) for k, v in mean_target_errors.items()},
            "max_probe_batch_probability_range": round(max_batch_range, 10),
            "max_mean_target_absolute_error": round(float(max_mean_error), 10),
            "max_probe_monte_carlo_standard_error": round(max_mc_se, 10),
            "certified_limits": {
                "minimum_simulations": DEFAULT_SIMULATIONS,
                "max_batch_probability_range": CERTIFIED_MAX_BATCH_PROBABILITY_RANGE,
                "max_mean_target_error": CERTIFIED_MAX_MEAN_TARGET_ERROR,
                "max_monte_carlo_standard_error": CERTIFIED_MAX_MONTE_CARLO_SE,
            },
            "converged": converged,
        },
        "provenance": {
            "step8c_projection_content_sha256": adjusted.get("projection_content_sha256"),
            "step8b_official_box_baseline_content_sha256": baseline.get("baseline_content_sha256"),
            "official_recent_game_ids": baseline.get("selected_game_ids"),
            "third_party_sources_used": False,
        },
        "guardrails": {
            "official_integer_box_counts_only_for_dispersion_and_dependence": True,
            "small_sample_variance_regularized_toward_poisson": True,
            "small_sample_correlation_regularized_toward_independence": True,
            "p_r_a_not_simulated_independently": True,
            "pra_recomposed_from_same_joint_p_r_a_draws": True,
            "sportsbook_data_used": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_enabled": False,
            "production_activation_allowed": False,
        },
    }
    hash_surface = dict(result)
    hash_surface.pop("generated_at_utc", None)
    result["result_content_sha256"] = _canonical_hash(hash_surface)
    _assert_safe_environment(env)
    return result


def probability_for_line(result: Mapping[str, Any], stat: str, line: float) -> dict[str, Any]:
    """Evaluate over/push/under from a completed Step-8D probability mass table."""
    if stat not in (*_STATS, _PRA):
        raise ValueError(f"unsupported stat {stat!r}")
    distributions = result.get("distributions")
    distribution = distributions.get(stat) if isinstance(distributions, Mapping) else None
    rows = distribution.get("probability_mass") if isinstance(distribution, Mapping) else None
    simulations = ((result.get("simulation") or {}).get("simulations") if isinstance(result, Mapping) else None)
    if not isinstance(rows, list) or not isinstance(simulations, int) or simulations <= 0:
        raise ValueError("result is missing a valid Step-8D distribution")
    if float(line).is_integer():
        integer = int(line)
        under = sum(float(row["probability"]) for row in rows if int(row["value"]) < integer)
        push = sum(float(row["probability"]) for row in rows if int(row["value"]) == integer)
        over = sum(float(row["probability"]) for row in rows if int(row["value"]) > integer)
    else:
        under = sum(float(row["probability"]) for row in rows if int(row["value"]) < line)
        push = 0.0
        over = sum(float(row["probability"]) for row in rows if int(row["value"]) > line)
    return {
        "stat": stat,
        "line": float(line),
        "under_probability": round(under, 10),
        "push_probability": round(push, 10),
        "over_probability": round(over, 10),
    }


def get_player_game_step8_joint_probability_distribution(
    player_id: int,
    game_id: str,
    *,
    simulations: int = DEFAULT_SIMULATIONS,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    """Live first-party wrapper. Still isolated and production-OFF by design."""
    _assert_safe_environment()
    handoff = get_player_game_step8_projection_handoff(int(player_id), str(game_id))
    baseline = build_step8_official_box_baseline(handoff)
    adjusted = build_step8_context_adjusted_projection(handoff, baseline)
    return simulate_step8_joint_distribution(
        adjusted,
        baseline,
        simulations=simulations,
        batch_size=batch_size,
    )
