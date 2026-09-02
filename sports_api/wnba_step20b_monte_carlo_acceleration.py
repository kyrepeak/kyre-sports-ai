"""WNBA Step20B semantics-preserving acceleration for frozen Step8D Monte Carlo.

The frozen Step8D implementation maps each correlated latent-normal draw through
its existing Abramowitz-Stegun normal-CDF approximation and then through a
discrete marginal CDF table. Because that CDF approximation is monotone, the
same discrete result can be obtained by inverting the *same approximation* once
for each marginal CDF boundary and searching the latent normal draw directly.

This removes the expensive 15,000,000-element normal-CDF transform from a
5,000,000-draw P/R/A run while preserving:
- the same PCG64 random stream and seed;
- the same Gaussian-copula latent draws and Cholesky transform;
- the same marginal CDF tables and discrete search semantics;
- the same 5,000,000 simulations and 250,000 batch size;
- the same result contract, model version, convergence rules, and content hash.

The installer patches only ``step8d.simulate_step8_joint_distribution``. It does
not modify projection math, readiness, provider data, persistence, sportsbook
transport, or wagering behavior.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import threading
from typing import Any, Callable, Mapping

import numpy as np

from sports_api import wnba_step8_joint_monte_carlo as step8d

SOURCE = "Kyre Sports API WNBA Step20B frozen Step8D latent-threshold acceleration"
MODEL_VERSION = "wnba_step20b_step8d_latent_threshold_acceleration_v1"

_ORIGINAL_SIMULATE: Callable[..., dict[str, Any]] = step8d.simulate_step8_joint_distribution
_LOCK = threading.RLock()
_INSTALLED = False
_CALL_COUNT = 0


def _latent_threshold_table(cdf: np.ndarray) -> np.ndarray:
    """Invert Step8D's existing monotone normal-CDF approximation once.

    The final discrete count mapping is then ``searchsorted(thresholds, z)``
    instead of ``searchsorted(cdf, Phi_approx(z))``. We deliberately invert the
    frozen approximation itself rather than using an exact-normal PPF, so the
    old Step8D count boundaries are retained.
    """
    probabilities = np.asarray(cdf, dtype=np.float64)
    if probabilities.ndim != 1 or probabilities.size == 0:
        raise step8d.WNBAStep8MonteCarloUpstreamError(
            "Step20B latent-threshold acceleration requires a one-dimensional marginal CDF."
        )
    if np.any(~np.isfinite(probabilities)) or np.any(np.diff(probabilities) < 0.0):
        raise step8d.WNBAStep8MonteCarloUpstreamError(
            "Step20B latent-threshold acceleration received an invalid marginal CDF."
        )
    if float(probabilities[-1]) != 1.0:
        raise step8d.WNBAStep8MonteCarloUpstreamError(
            "Step20B latent-threshold acceleration requires the frozen marginal CDF to end at 1."
        )

    thresholds = np.empty_like(probabilities)
    low_mask = probabilities <= 0.0
    high_mask = probabilities >= 1.0
    finite_mask = ~(low_mask | high_mask)
    thresholds[low_mask] = -np.inf
    thresholds[high_mask] = np.inf

    if np.any(finite_mask):
        targets = probabilities[finite_mask]
        # +/- 12 is far beyond every probability boundary Step8D can retain at
        # its 1e-12 marginal-tail cutoff. Bisection is deterministic and happens
        # only once per short marginal table, not per Monte Carlo draw.
        lo = np.full(targets.shape, -12.0, dtype=np.float64)
        hi = np.full(targets.shape, 12.0, dtype=np.float64)
        for _ in range(80):
            mid = (lo + hi) * 0.5
            values = step8d._standard_normal_cdf(mid)
            move_lo = values < targets
            lo = np.where(move_lo, mid, lo)
            hi = np.where(move_lo, hi, mid)
        thresholds[finite_mask] = (lo + hi) * 0.5

    if np.any(np.diff(thresholds) < 0.0):
        raise step8d.WNBAStep8MonteCarloUpstreamError(
            "Step20B latent-threshold inversion produced nonmonotone boundaries."
        )
    return thresholds


def _counts_from_latent(
    normals: np.ndarray,
    latent_thresholds: list[np.ndarray],
) -> np.ndarray:
    counts = np.empty((normals.shape[0], 3), dtype=np.int16)
    for index, thresholds in enumerate(latent_thresholds):
        counts[:, index] = np.searchsorted(
            thresholds,
            normals[:, index],
            side="left",
        ).astype(np.int16)
    return counts


def simulate_step8_joint_distribution_accelerated(
    adjusted: Mapping[str, Any],
    baseline: Mapping[str, Any],
    *,
    simulations: int = step8d.DEFAULT_SIMULATIONS,
    batch_size: int = step8d.DEFAULT_BATCH_SIZE,
    seed: int | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run frozen Step8D with an equivalent direct latent-threshold mapping."""
    global _CALL_COUNT
    step8d._assert_safe_environment(env)
    if simulations < step8d.MIN_SIMULATIONS:
        raise ValueError(f"Step 8D requires at least {step8d.MIN_SIMULATIONS:,} simulations.")
    if batch_size <= 0 or batch_size > simulations:
        raise ValueError("Step 8D batch_size must be positive and no larger than simulations.")

    game_id, player_id, target, history = step8d._validate_inputs(adjusted, baseline)
    spec = step8d._build_model_spec(target, history)
    latent_corr = spec["regularized_latent_correlation"]
    cholesky = np.linalg.cholesky(latent_corr)
    cdf_tables = [step8d._cdf_table(spec["marginals"][stat]) for stat in step8d._STATS]
    latent_thresholds = [_latent_threshold_table(cdf) for cdf in cdf_tables]

    actual_seed = int(step8d._seed_from_inputs(adjusted, baseline) if seed is None else seed)
    rng = np.random.default_rng(actual_seed)
    histograms: dict[str, np.ndarray] = {
        stat: np.zeros(1, dtype=np.int64) for stat in (*step8d._STATS, step8d._PRA)
    }
    stat_sums = np.zeros(3, dtype=np.float64)
    cross_sums = np.zeros((3, 3), dtype=np.float64)
    probe_thresholds = np.asarray(
        [math.ceil(target[stat]) for stat in step8d._STATS], dtype=np.int64
    )
    pra_probe_threshold = int(math.ceil(target[step8d._PRA]))
    batch_probe_probabilities: list[list[float]] = []
    batch_means: list[list[float]] = []
    batch_sizes: list[int] = []

    remaining = int(simulations)
    while remaining > 0:
        current = min(int(batch_size), remaining)
        normals = rng.standard_normal((current, 3)) @ cholesky.T
        counts = _counts_from_latent(normals, latent_thresholds)
        pra = counts.sum(axis=1, dtype=np.int32)

        for index, stat in enumerate(step8d._STATS):
            local = np.bincount(counts[:, index].astype(np.int64))
            if local.size > histograms[stat].size:
                histograms[stat] = np.pad(
                    histograms[stat], (0, local.size - histograms[stat].size)
                )
            histograms[stat][: local.size] += local
        local_pra = np.bincount(pra.astype(np.int64))
        if local_pra.size > histograms[step8d._PRA].size:
            histograms[step8d._PRA] = np.pad(
                histograms[step8d._PRA],
                (0, local_pra.size - histograms[step8d._PRA].size),
            )
        histograms[step8d._PRA][: local_pra.size] += local_pra

        as_float = counts.astype(np.float64)
        stat_sums += np.sum(as_float, axis=0)
        cross_sums += as_float.T @ as_float
        probes = [
            float(np.mean(counts[:, i] >= probe_thresholds[i])) for i in range(3)
        ]
        probes.append(float(np.mean(pra >= pra_probe_threshold)))
        batch_probe_probabilities.append(probes)
        component_means = np.mean(as_float, axis=0)
        batch_means.append(
            [
                float(component_means[0]),
                float(component_means[1]),
                float(component_means[2]),
                float(np.mean(pra)),
            ]
        )
        batch_sizes.append(current)
        remaining -= current

    distributions = {
        stat: step8d._hist_summary(histograms[stat], simulations)
        for stat in (*step8d._STATS, step8d._PRA)
    }
    achieved_means = stat_sums / float(simulations)
    achieved_covariance = (
        cross_sums / float(simulations) - np.outer(achieved_means, achieved_means)
    )
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
    probe_names = (*step8d._STATS, step8d._PRA)
    probe_probabilities: dict[str, float] = {}
    probe_standard_errors: dict[str, float] = {}
    batch_ranges: dict[str, float] = {}
    for index, stat in enumerate(probe_names):
        threshold = int(probe_thresholds[index]) if index < 3 else pra_probe_threshold
        hist = histograms[stat]
        probability = float(hist[np.arange(hist.size) >= threshold].sum()) / float(simulations)
        probe_probabilities[stat] = probability
        probe_standard_errors[stat] = math.sqrt(
            max(probability * (1.0 - probability), 0.0) / simulations
        )
        batch_ranges[stat] = float(
            np.max(batch_array[:, index]) - np.min(batch_array[:, index])
        )

    mean_target_errors = {
        stat: abs(distributions[stat]["expected"] - target[stat])
        for stat in (*step8d._STATS, step8d._PRA)
    }
    max_batch_range = max(batch_ranges.values())
    max_mean_error = max(mean_target_errors.values())
    max_mc_se = max(probe_standard_errors.values())
    converged = bool(
        simulations >= step8d.DEFAULT_SIMULATIONS
        and max_batch_range <= step8d.CERTIFIED_MAX_BATCH_PROBABILITY_RANGE
        and max_mean_error <= step8d.CERTIFIED_MAX_MEAN_TARGET_ERROR
        and max_mc_se <= step8d.CERTIFIED_MAX_MONTE_CARLO_SE
    )

    line_examples = {
        stat: step8d._line_probability_from_hist(
            histograms[stat], simulations, math.floor(target[stat]) + 0.5
        )
        for stat in (*step8d._STATS, step8d._PRA)
    }
    result = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": step8d.SCHEMA_VERSION,
        "source": step8d.SOURCE,
        "model_version": step8d.MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "game_id": game_id,
        "player_id": player_id,
        "team_key": adjusted.get("team_key"),
        "opponent_team_key": adjusted.get("opponent_team_key"),
        "step8c_target": {
            "projection_id": adjusted.get("projection_id"),
            "projection_content_sha256": adjusted.get("projection_content_sha256"),
            **{
                stat: round(float(target[stat]), 8)
                for stat in (*step8d._STATS, step8d._PRA)
            },
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
                for stat in step8d._STATS
            },
            "empirical_correlation": {
                left: {
                    right: round(float(spec["empirical_correlation"][i, j]), 8)
                    for j, right in enumerate(step8d._STATS)
                }
                for i, left in enumerate(step8d._STATS)
            },
            "regularized_latent_correlation": {
                left: {
                    right: round(float(spec["regularized_latent_correlation"][i, j]), 8)
                    for j, right in enumerate(step8d._STATS)
                }
                for i, left in enumerate(step8d._STATS)
            },
            "regularized_correlation_eigenvalues": [
                round(float(value), 8)
                for value in spec["regularized_correlation_eigenvalues"]
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
            "marginal_inverse_cdf_tail_epsilon": step8d.CDF_TAIL_EPSILON,
        },
        "distributions": distributions,
        "example_half_point_lines_near_target": line_examples,
        "achieved_joint_dependence": {
            "correlation": {
                left: {
                    right: round(float(achieved_corr[i, j]), 8)
                    for j, right in enumerate(step8d._STATS)
                }
                for i, left in enumerate(step8d._STATS)
            }
        },
        "convergence": {
            "probe_thresholds_at_least": {
                "points": int(probe_thresholds[0]),
                "rebounds": int(probe_thresholds[1]),
                "assists": int(probe_thresholds[2]),
                step8d._PRA: pra_probe_threshold,
            },
            "probe_probabilities": {
                k: round(v, 10) for k, v in probe_probabilities.items()
            },
            "probe_monte_carlo_standard_errors": {
                k: round(v, 10) for k, v in probe_standard_errors.items()
            },
            "probe_batch_probability_ranges": {
                k: round(v, 10) for k, v in batch_ranges.items()
            },
            "mean_target_absolute_errors": {
                k: round(float(v), 10) for k, v in mean_target_errors.items()
            },
            "max_probe_batch_probability_range": round(max_batch_range, 10),
            "max_mean_target_absolute_error": round(float(max_mean_error), 10),
            "max_probe_monte_carlo_standard_error": round(max_mc_se, 10),
            "certified_limits": {
                "minimum_simulations": step8d.DEFAULT_SIMULATIONS,
                "max_batch_probability_range": step8d.CERTIFIED_MAX_BATCH_PROBABILITY_RANGE,
                "max_mean_target_error": step8d.CERTIFIED_MAX_MEAN_TARGET_ERROR,
                "max_monte_carlo_standard_error": step8d.CERTIFIED_MAX_MONTE_CARLO_SE,
            },
            "converged": converged,
        },
        "provenance": {
            "step8c_projection_content_sha256": adjusted.get("projection_content_sha256"),
            "step8b_official_box_baseline_content_sha256": baseline.get(
                "baseline_content_sha256"
            ),
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
    result["result_content_sha256"] = step8d._canonical_hash(hash_surface)
    step8d._assert_safe_environment(env)
    with _LOCK:
        _CALL_COUNT += 1
    return result


def install_step20b_monte_carlo_acceleration() -> dict[str, Any]:
    global _INSTALLED
    with _LOCK:
        current = step8d.simulate_step8_joint_distribution
        if current is simulate_step8_joint_distribution_accelerated:
            _INSTALLED = True
        elif current is _ORIGINAL_SIMULATE:
            step8d.simulate_step8_joint_distribution = simulate_step8_joint_distribution_accelerated
            _INSTALLED = True
        else:
            raise RuntimeError(
                "Step20B Monte Carlo acceleration refuses an unknown Step8D simulator override."
            )
    return installation_status()


def installation_status() -> dict[str, Any]:
    with _LOCK:
        installed = bool(_INSTALLED)
        call_count = int(_CALL_COUNT)
    return {
        "data_type": "wnba_step20b_monte_carlo_acceleration_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "installed": installed,
        "binding_active": bool(
            installed
            and step8d.simulate_step8_joint_distribution
            is simulate_step8_joint_distribution_accelerated
        ),
        "call_count": call_count,
        "guardrails": {
            "frozen_step8d_model_version_preserved": True,
            "same_pcg64_random_stream": True,
            "same_latent_gaussian_draws": True,
            "same_marginal_cdf_tables": True,
            "same_discrete_count_mapping_required": True,
            "normal_cdf_approximation_inverted_once_not_replaced": True,
            "simulations_modified": False,
            "batch_size_modified": False,
            "projection_math_modified": False,
            "readiness_relaxed": False,
            "sportsbook_transport_modified": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


__all__ = [
    "MODEL_VERSION",
    "SOURCE",
    "install_step20b_monte_carlo_acceleration",
    "installation_status",
    "simulate_step8_joint_distribution_accelerated",
]
