"""Step 5E: correlated WNBA Monte Carlo player outcome engine.

Uses the frozen Step 5C scenario centers and Step 5D empirical complete-game
P/R/A observations. Simulations use a joint empirical ratio bootstrap: one
historical row index is sampled for P/R/A together, each stat is scaled by its
scenario target mean, then stochastic integer rounding is applied. PRA is always
reconstructed as P + R + A.

LOW/BASE/HIGH are separate conditional scenario distributions. Step 5E does not
invent probabilities for the Step 5C scenarios, use sportsbook data, or create
betting edges.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from math import ceil, sqrt
from typing import Any

import numpy as np

from sports_api.wnba_empirical_outcome_distribution import (
    MODEL_VERSION as EMPIRICAL_MODEL_VERSION,
    WNBAEmpiricalDistributionModelInputError,
    WNBAEmpiricalDistributionNotFoundError,
    WNBAEmpiricalDistributionNotReadyError,
    WNBAEmpiricalDistributionUpstreamError,
    build_empirical_outcome_distribution,
)
from sports_api.wnba_game_history import (
    ALLOWED_SEASON_TYPES,
    WNBAHistoryNotFoundError,
    WNBAHistoryUpstreamError,
    get_player_game_log_dataset,
)
from sports_api.wnba_model_input_readiness import (
    DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
    WNBAModelInputReadinessNotFoundError,
    WNBAModelInputReadinessUpstreamError,
    get_player_game_model_input_readiness,
)
from sports_api.wnba_projection_scenarios import (
    MODEL_VERSION as SCENARIO_MODEL_VERSION,
    WNBAProjectionScenarioModelInputError,
    WNBAProjectionScenarioNotReadyError,
    WNBAProjectionScenarioUpstreamError,
    project_scenarios_from_readiness,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5E correlated Monte Carlo outcome engine"
MODEL_VERSION = "wnba_step_5e_correlated_monte_carlo_v1"
MODEL_FAMILY = "joint_empirical_ratio_bootstrap"
MAX_RECENT_GAMES = 20
MIN_DISTRIBUTION_GAMES = 1
MAX_DISTRIBUTION_GAMES = 50

DEFAULT_SIMULATION_COUNT = 5_000_000
MIN_SIMULATION_COUNT = 1_000
MAX_SIMULATION_COUNT = 10_000_000
DEFAULT_BATCH_SIZE = 250_000
MIN_BATCH_SIZE = 1_000
MAX_BATCH_SIZE = 1_000_000
DEFAULT_RANDOM_SEED = 56001

MIN_JOINT_EMPIRICAL_GAMES = 3
MAX_MEAN_TARGET_ERROR = 0.10
MAX_MEAN_MC_STANDARD_ERROR = 0.01
MAX_BATCH_MEAN_RANGE = 0.10
MIN_CONVERGENCE_SIMULATIONS = 100_000

STAT_KEYS = ("points", "rebounds", "assists")
OUTPUT_KEYS = ("points", "rebounds", "assists", "pra")
SCENARIO_KEYS = ("low", "base", "high")


class WNBACorrelatedMonteCarloNotReadyError(RuntimeError):
    pass


class WNBACorrelatedMonteCarloNotFoundError(LookupError):
    pass


class WNBACorrelatedMonteCarloUpstreamError(RuntimeError):
    pass


class WNBACorrelatedMonteCarloModelInputError(RuntimeError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number


def _positive_player_id(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _game_id(value: str) -> str:
    result = str(value).strip()
    if len(result) != 10 or not result.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return result


def _last_n(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_RECENT_GAMES:
        raise ValueError("WNBA last_n_games must be an integer from 1 through 20.")
    return value


def _distribution_last_n(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not MIN_DISTRIBUTION_GAMES <= value <= MAX_DISTRIBUTION_GAMES
    ):
        raise ValueError("WNBA distribution_last_n_games must be an integer from 1 through 50.")
    return value


def _simulation_count(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not MIN_SIMULATION_COUNT <= value <= MAX_SIMULATION_COUNT
    ):
        raise ValueError(
            f"WNBA simulation_count must be an integer from "
            f"{MIN_SIMULATION_COUNT:,} through {MAX_SIMULATION_COUNT:,}."
        )
    return value


def _batch_size(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not MIN_BATCH_SIZE <= value <= MAX_BATCH_SIZE
    ):
        raise ValueError(
            f"WNBA batch_size must be an integer from "
            f"{MIN_BATCH_SIZE:,} through {MAX_BATCH_SIZE:,}."
        )
    return value


def _random_seed(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 <= value <= 4_294_967_295
    ):
        raise ValueError("WNBA random_seed must be an integer from 0 through 4294967295.")
    return value


def _choice(value: str, allowed: tuple[str, ...], label: str) -> str:
    lookup = {item.casefold(): item for item in allowed}
    result = lookup.get(str(value).strip().casefold())
    if result is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return result


def _bool(value: bool, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"WNBA {label} must be boolean.")
    return value


def _max_snapshot_age(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 1440:
        raise ValueError("WNBA max_snapshot_age_minutes must be an integer from 1 through 1440.")
    return value


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dig(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _valid_sha256(value: Any) -> bool:
    text = _clean(value)
    return bool(
        text
        and len(text) == 64
        and all(ch in "0123456789abcdefABCDEF" for ch in text)
    )


def _validate_scenario_distribution_identity(
    scenarios: dict[str, Any],
    distribution: dict[str, Any],
) -> tuple[int, str, str, str]:
    if not isinstance(scenarios, dict) or scenarios.get("model_version") != SCENARIO_MODEL_VERSION:
        raise WNBACorrelatedMonteCarloUpstreamError(
            "Step 5E received an unexpected Step 5C model version."
        )
    if not isinstance(distribution, dict) or distribution.get("model_version") != EMPIRICAL_MODEL_VERSION:
        raise WNBACorrelatedMonteCarloUpstreamError(
            "Step 5E received an unexpected Step 5D model version."
        )

    player_id = _to_int(distribution.get("player_id"))
    game_id = _clean(distribution.get("game_id"))
    team_key = _clean(distribution.get("team_key"))
    opponent_key = _clean(distribution.get("opponent_team_key"))
    if (
        player_id is None
        or player_id <= 0
        or not game_id
        or not team_key
        or not opponent_key
        or team_key == opponent_key
    ):
        raise WNBACorrelatedMonteCarloUpstreamError(
            "Step 5D player/game/team identity is malformed."
        )

    for key, expected in (
        ("player_id", player_id),
        ("game_id", game_id),
        ("team_key", team_key),
        ("opponent_team_key", opponent_key),
    ):
        observed = scenarios.get(key)
        if key == "player_id":
            observed = _to_int(observed)
        else:
            observed = _clean(observed)
        if observed != expected:
            raise WNBACorrelatedMonteCarloUpstreamError(
                f"Step 5C and Step 5D disagree on {key}."
            )

    scenario_ref = distribution.get("step_5c_scenario_reference")
    if not isinstance(scenario_ref, dict):
        raise WNBACorrelatedMonteCarloUpstreamError(
            "Step 5D is missing its Step 5C scenario reference."
        )
    if scenario_ref.get("model_version") != SCENARIO_MODEL_VERSION:
        raise WNBACorrelatedMonteCarloUpstreamError(
            "Step 5D references an unexpected Step 5C model version."
        )
    for key in ("scenario_id", "scenario_fingerprint_sha256"):
        if scenario_ref.get(key) != scenarios.get(key):
            raise WNBACorrelatedMonteCarloUpstreamError(
                f"Step 5D Step-5C reference disagrees on {key}."
            )
    if not _valid_sha256(distribution.get("distribution_fingerprint_sha256")):
        raise WNBACorrelatedMonteCarloUpstreamError(
            "Step 5D distribution fingerprint is missing or invalid."
        )
    if not _valid_sha256(scenarios.get("scenario_fingerprint_sha256")):
        raise WNBACorrelatedMonteCarloUpstreamError(
            "Step 5C scenario fingerprint is missing or invalid."
        )

    dist_snapshot = distribution.get("snapshot_reference")
    scenario_snapshot = scenarios.get("snapshot_reference")
    if not isinstance(dist_snapshot, dict) or not isinstance(scenario_snapshot, dict):
        raise WNBACorrelatedMonteCarloUpstreamError(
            "Step 5C/5D snapshot reference is missing."
        )
    for key in ("snapshot_id", "content_sha256", "game_id", "player_id", "recent_window_games"):
        if dist_snapshot.get(key) != scenario_snapshot.get(key):
            raise WNBACorrelatedMonteCarloUpstreamError(
                f"Step 5C and Step 5D snapshot references disagree on {key}."
            )
    return player_id, game_id, team_key, opponent_key


def _scenario_targets(scenarios: dict[str, Any]) -> dict[str, dict[str, float]]:
    raw = scenarios.get("scenarios")
    if not isinstance(raw, dict):
        raise WNBACorrelatedMonteCarloUpstreamError(
            "Step 5C scenarios object is missing."
        )
    out: dict[str, dict[str, float]] = {}
    for scenario_name in SCENARIO_KEYS:
        row = raw.get(scenario_name)
        if not isinstance(row, dict):
            raise WNBACorrelatedMonteCarloUpstreamError(
                f"Step 5C is missing {scenario_name.upper()} scenario."
            )
        values: dict[str, float] = {}
        for stat in OUTPUT_KEYS:
            value = _to_float(row.get(stat))
            if value is None or value < 0:
                raise WNBACorrelatedMonteCarloUpstreamError(
                    f"Step 5C {scenario_name}.{stat} is invalid."
                )
            values[stat] = value
        if abs(values["pra"] - sum(values[key] for key in STAT_KEYS)) > 0.001:
            raise WNBACorrelatedMonteCarloUpstreamError(
                f"Step 5C {scenario_name.upper()} PRA does not equal P+R+A."
            )
        out[scenario_name] = values
    for stat in OUTPUT_KEYS:
        if not (
            out["low"][stat] <= out["base"][stat] <= out["high"][stat]
        ):
            raise WNBACorrelatedMonteCarloUpstreamError(
                f"Step 5C scenario ordering is invalid for {stat}."
            )
    return out


def _observed_matrix(
    distribution: dict[str, Any],
) -> tuple[np.ndarray, list[dict[str, Any]], np.ndarray]:
    observations = distribution.get("observations")
    if not isinstance(observations, list) or not observations:
        raise WNBACorrelatedMonteCarloNotReadyError(
            "Step 5D contains no empirical observations for Monte Carlo."
        )
    if len(observations) < MIN_JOINT_EMPIRICAL_GAMES:
        raise WNBACorrelatedMonteCarloNotReadyError(
            f"Step 5E requires at least {MIN_JOINT_EMPIRICAL_GAMES} complete empirical games "
            "for correlated Monte Carlo."
        )
    matrix_rows: list[list[float]] = []
    normalized_rows: list[dict[str, Any]] = []
    seen_game_ids: set[str] = set()
    for row in observations:
        if not isinstance(row, dict):
            raise WNBACorrelatedMonteCarloUpstreamError(
                "Step 5D observations contain a malformed row."
            )
        game_id = _clean(row.get("game_id"))
        if not game_id or game_id in seen_game_ids:
            raise WNBACorrelatedMonteCarloUpstreamError(
                "Step 5D observations contain a missing or duplicate game ID."
            )
        seen_game_ids.add(game_id)
        values = []
        for stat in STAT_KEYS:
            value = _to_float(row.get(stat))
            if value is None or value < 0:
                raise WNBACorrelatedMonteCarloUpstreamError(
                    f"Step 5D observation {game_id} has invalid {stat}."
                )
            values.append(value)
        pra = _to_float(row.get("pra"))
        if pra is None or abs(pra - sum(values)) > 0.001:
            raise WNBACorrelatedMonteCarloUpstreamError(
                f"Step 5D observation {game_id} has inconsistent PRA."
            )
        matrix_rows.append(values)
        normalized_rows.append(
            {
                "game_id": game_id,
                "points": values[0],
                "rebounds": values[1],
                "assists": values[2],
                "pra": pra,
            }
        )

    matrix = np.asarray(matrix_rows, dtype=np.float64)
    means = matrix.mean(axis=0)
    if np.any(means <= 0):
        raise WNBACorrelatedMonteCarloNotReadyError(
            "Step 5E requires positive empirical P/R/A means for ratio-bootstrap scaling."
        )
    sample_variances = matrix.var(axis=0, ddof=1)
    zero_variance = [
        STAT_KEYS[index]
        for index, value in enumerate(sample_variances)
        if value <= 0
    ]
    if zero_variance:
        raise WNBACorrelatedMonteCarloNotReadyError(
            "Step 5E cannot build correlated Monte Carlo from zero-variance empirical stats: "
            + ", ".join(zero_variance)
            + "."
        )

    window = distribution.get("distribution_window")
    if isinstance(window, dict):
        selected_ids = window.get("selected_game_ids")
        if isinstance(selected_ids, list):
            observed_ids = [row["game_id"] for row in normalized_rows]
            if selected_ids != observed_ids:
                raise WNBACorrelatedMonteCarloUpstreamError(
                    "Step 5D selected_game_ids disagree with observation order/content."
                )

    summaries = distribution.get("summary_by_stat")
    if not isinstance(summaries, dict):
        raise WNBACorrelatedMonteCarloUpstreamError(
            "Step 5D summary_by_stat is missing."
        )
    for index, stat in enumerate(STAT_KEYS):
        summary = summaries.get(stat)
        if not isinstance(summary, dict):
            raise WNBACorrelatedMonteCarloUpstreamError(
                f"Step 5D summary is missing {stat}."
            )
        summary_mean = _to_float(summary.get("mean"))
        if summary_mean is None or abs(summary_mean - means[index]) > 1e-5:
            raise WNBACorrelatedMonteCarloUpstreamError(
                f"Step 5D {stat} empirical mean disagrees with observations."
            )

    correlation = np.corrcoef(matrix, rowvar=False)
    basis = _dig(distribution, "dependence", "p_r_a_monte_carlo_basis", "pearson_correlation_matrix")
    if not isinstance(basis, dict):
        raise WNBACorrelatedMonteCarloUpstreamError(
            "Step 5D P/R/A dependence basis is missing."
        )
    for left_index, left in enumerate(STAT_KEYS):
        row = basis.get(left)
        if not isinstance(row, dict):
            raise WNBACorrelatedMonteCarloUpstreamError(
                f"Step 5D correlation basis is missing {left}."
            )
        for right_index, right in enumerate(STAT_KEYS):
            expected = _to_float(row.get(right))
            if expected is None or abs(expected - correlation[left_index, right_index]) > 1e-6:
                raise WNBACorrelatedMonteCarloUpstreamError(
                    f"Step 5D correlation basis disagrees with observations for {left}/{right}."
                )

    quality = distribution.get("data_quality")
    if isinstance(quality, dict) and quality.get("dependence_ready_without_zero_variance") is False:
        raise WNBACorrelatedMonteCarloNotReadyError(
            "Step 5D marks the empirical dependence structure not ready for correlated simulation."
        )

    return matrix, normalized_rows, means


def _ensure_hist_capacity(existing: np.ndarray | None, incoming: np.ndarray) -> np.ndarray:
    required = len(incoming)
    if existing is None:
        return incoming.astype(np.int64, copy=True)
    if len(existing) < required:
        extended = np.zeros(required, dtype=np.int64)
        extended[: len(existing)] = existing
        existing = extended
    existing[:required] += incoming
    return existing


def _stochastic_round_nonnegative(
    continuous: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    clipped = np.maximum(continuous, 0.0)
    floor = np.floor(clipped)
    fractional = clipped - floor
    rounded = floor + (rng.random(clipped.shape) < fractional)
    return rounded.astype(np.int16)


def _hist_summary(hist: np.ndarray, simulation_count: int) -> dict[str, Any]:
    counts = hist.astype(np.int64)
    total = int(counts.sum())
    if total != simulation_count:
        raise WNBACorrelatedMonteCarloUpstreamError(
            "Monte Carlo histogram count does not equal requested simulations."
        )
    values = np.arange(len(counts), dtype=np.float64)
    sum_values = float(np.dot(values, counts))
    sum_sq = float(np.dot(values * values, counts))
    mean = sum_values / total
    population_variance = max(0.0, sum_sq / total - mean * mean)
    sample_variance = (
        max(0.0, (sum_sq - total * mean * mean) / (total - 1))
        if total > 1
        else None
    )
    cumulative = np.cumsum(counts)
    reverse = np.cumsum(counts[::-1])[::-1]
    nonzero = np.flatnonzero(counts)
    minimum = int(nonzero[0])
    maximum = int(nonzero[-1])
    highest = int(counts.max())
    modes = [int(value) for value in np.flatnonzero(counts == highest)]

    def quantile(probability: float) -> int:
        rank = max(1, int(ceil(probability * total)))
        return int(np.searchsorted(cumulative, rank, side="left"))

    rows = []
    for value in nonzero:
        count = int(counts[value])
        frequency = count / total
        tail = int(reverse[value]) / total
        rows.append(
            {
                "value": int(value),
                "count": count,
                "frequency": round(frequency, 10),
                "mc_standard_error_frequency": round(
                    sqrt(max(0.0, frequency * (1.0 - frequency) / total)), 10
                ),
                "tail_probability_at_or_above": round(tail, 10),
                "mc_standard_error_tail": round(
                    sqrt(max(0.0, tail * (1.0 - tail) / total)), 10
                ),
            }
        )

    return {
        "simulation_count": total,
        "mean": round(mean, 6),
        "median": quantile(0.50),
        "modes": modes,
        "minimum": minimum,
        "maximum": maximum,
        "population_variance": round(population_variance, 8),
        "population_stddev": round(sqrt(population_variance), 8),
        "sample_variance": round(sample_variance, 8) if sample_variance is not None else None,
        "sample_stddev": round(sqrt(sample_variance), 8) if sample_variance is not None else None,
        "mc_standard_error_of_mean": round(
            sqrt(sample_variance / total) if sample_variance is not None else 0.0,
            10,
        ),
        "simulated_quantiles": {
            "p05": quantile(0.05),
            "p10": quantile(0.10),
            "p25": quantile(0.25),
            "p50": quantile(0.50),
            "p75": quantile(0.75),
            "p90": quantile(0.90),
            "p95": quantile(0.95),
            "method": "nearest_rank_from_simulated_integer_histogram",
        },
        "simulated_distribution": rows,
    }


def _sample_matrix_summary(
    count: int,
    sums: np.ndarray,
    cross_products: np.ndarray,
) -> dict[str, Any]:
    means = sums / count
    centered = cross_products - count * np.outer(means, means)
    sample_covariance = centered / (count - 1) if count > 1 else np.zeros((4, 4))
    diagonal = np.diag(sample_covariance)
    std = np.sqrt(np.maximum(diagonal, 0.0))
    denominator = np.outer(std, std)
    with np.errstate(divide="ignore", invalid="ignore"):
        correlation = np.where(denominator > 0, sample_covariance / denominator, np.nan)

    covariance_out: dict[str, dict[str, float | None]] = {}
    correlation_out: dict[str, dict[str, float | None]] = {}
    for i, left in enumerate(OUTPUT_KEYS):
        covariance_out[left] = {}
        correlation_out[left] = {}
        for j, right in enumerate(OUTPUT_KEYS):
            cov = float(sample_covariance[i, j])
            corr = float(correlation[i, j])
            covariance_out[left][right] = round(cov, 8)
            correlation_out[left][right] = round(corr, 8) if np.isfinite(corr) else None

    return {
        "sample_covariance_matrix": covariance_out,
        "pearson_correlation_matrix": correlation_out,
        "pra_is_reconstructed_sum": True,
        "p_r_a_only_basis": {
            "sample_covariance_matrix": {
                left: {right: covariance_out[left][right] for right in STAT_KEYS}
                for left in STAT_KEYS
            },
            "pearson_correlation_matrix": {
                left: {right: correlation_out[left][right] for right in STAT_KEYS}
                for left in STAT_KEYS
            },
        },
    }


def _scenario_convergence(
    targets: dict[str, float],
    summaries: dict[str, dict[str, Any]],
    batch_means: dict[str, list[float]],
    simulation_count: int,
) -> dict[str, Any]:
    target_errors = {
        stat: abs(summaries[stat]["mean"] - targets[stat])
        for stat in OUTPUT_KEYS
    }
    mean_mc_se = {
        stat: summaries[stat]["mc_standard_error_of_mean"]
        for stat in OUTPUT_KEYS
    }
    batch_ranges = {
        stat: (
            max(batch_means[stat]) - min(batch_means[stat])
            if batch_means[stat]
            else None
        )
        for stat in OUTPUT_KEYS
    }
    enough_sims = simulation_count >= MIN_CONVERGENCE_SIMULATIONS
    target_alignment = all(value <= MAX_MEAN_TARGET_ERROR for value in target_errors.values())
    se_ok = all(value <= MAX_MEAN_MC_STANDARD_ERROR for value in mean_mc_se.values())
    batch_ok = all(
        value is not None and value <= MAX_BATCH_MEAN_RANGE
        for value in batch_ranges.values()
    )
    return {
        "converged": bool(enough_sims and target_alignment and se_ok and batch_ok),
        "minimum_simulations_for_convergence_label": MIN_CONVERGENCE_SIMULATIONS,
        "simulation_count_threshold_met": enough_sims,
        "mean_target_alignment_passed": target_alignment,
        "mean_mc_standard_error_passed": se_ok,
        "batch_mean_range_passed": batch_ok,
        "absolute_mean_target_error_by_stat": {
            key: round(value, 8) for key, value in target_errors.items()
        },
        "mc_standard_error_of_mean_by_stat": mean_mc_se,
        "max_minus_min_batch_mean_by_stat": {
            key: round(value, 8) if value is not None else None
            for key, value in batch_ranges.items()
        },
        "thresholds": {
            "maximum_absolute_mean_target_error": MAX_MEAN_TARGET_ERROR,
            "maximum_mc_standard_error_of_mean": MAX_MEAN_MC_STANDARD_ERROR,
            "maximum_batch_mean_range": MAX_BATCH_MEAN_RANGE,
        },
        "semantics": (
            "Convergence is a Monte Carlo numerical-stability check. It is not model "
            "calibration, predictive accuracy, or confidence in the basketball projection."
        ),
    }


def simulate_correlated_outcomes(
    scenarios: dict[str, Any],
    distribution: dict[str, Any],
    *,
    simulation_count: int = DEFAULT_SIMULATION_COUNT,
    batch_size: int = DEFAULT_BATCH_SIZE,
    random_seed: int = DEFAULT_RANDOM_SEED,
) -> dict[str, Any]:
    simulation_count = _simulation_count(simulation_count)
    batch_size = _batch_size(batch_size)
    random_seed = _random_seed(random_seed)
    player_id, game_id, team_key, opponent_key = _validate_scenario_distribution_identity(
        scenarios, distribution
    )
    targets = _scenario_targets(scenarios)
    observed, observation_rows, empirical_means = _observed_matrix(distribution)

    ratios = observed / empirical_means
    if not np.all(np.isfinite(ratios)) or np.any(ratios < 0):
        raise WNBACorrelatedMonteCarloUpstreamError(
            "Step 5D produced invalid empirical P/R/A ratio vectors."
        )

    rng = np.random.default_rng(random_seed)
    histograms: dict[str, dict[str, np.ndarray | None]] = {
        scenario: {stat: None for stat in OUTPUT_KEYS}
        for scenario in SCENARIO_KEYS
    }
    sums: dict[str, np.ndarray] = {
        scenario: np.zeros(4, dtype=np.float64) for scenario in SCENARIO_KEYS
    }
    cross_products: dict[str, np.ndarray] = {
        scenario: np.zeros((4, 4), dtype=np.float64) for scenario in SCENARIO_KEYS
    }
    batch_means: dict[str, dict[str, list[float]]] = {
        scenario: {stat: [] for stat in OUTPUT_KEYS}
        for scenario in SCENARIO_KEYS
    }

    remaining = simulation_count
    batch_count = 0
    while remaining > 0:
        current = min(batch_size, remaining)
        indices = rng.integers(0, len(ratios), size=current, endpoint=False)
        sampled_ratios = ratios[indices]
        for scenario_name in SCENARIO_KEYS:
            target_vector = np.asarray(
                [targets[scenario_name][stat] for stat in STAT_KEYS],
                dtype=np.float64,
            )
            continuous = sampled_ratios * target_vector
            rounded = _stochastic_round_nonnegative(continuous, rng)
            pra = rounded.sum(axis=1, dtype=np.int32).astype(np.int16)
            four = np.column_stack((rounded, pra)).astype(np.float64)

            sums[scenario_name] += four.sum(axis=0)
            cross_products[scenario_name] += four.T @ four
            means = four.mean(axis=0)
            for index, stat in enumerate(OUTPUT_KEYS):
                batch_means[scenario_name][stat].append(float(means[index]))
                bincount = np.bincount(four[:, index].astype(np.int32))
                histograms[scenario_name][stat] = _ensure_hist_capacity(
                    histograms[scenario_name][stat], bincount
                )
        remaining -= current
        batch_count += 1

    scenario_results: dict[str, Any] = {}
    convergence_states: dict[str, bool] = {}
    for scenario_name in SCENARIO_KEYS:
        stat_summaries: dict[str, Any] = {}
        for stat in OUTPUT_KEYS:
            histogram = histograms[scenario_name][stat]
            if histogram is None:
                raise WNBACorrelatedMonteCarloUpstreamError(
                    "Monte Carlo histogram was not created."
                )
            stat_summaries[stat] = _hist_summary(histogram, simulation_count)
        dependence = _sample_matrix_summary(
            simulation_count,
            sums[scenario_name],
            cross_products[scenario_name],
        )
        convergence = _scenario_convergence(
            targets[scenario_name],
            stat_summaries,
            batch_means[scenario_name],
            simulation_count,
        )
        convergence_states[scenario_name] = convergence["converged"]
        scenario_results[scenario_name] = {
            "conditional_scenario": scenario_name,
            "target_means": {
                key: round(targets[scenario_name][key], 6) for key in OUTPUT_KEYS
            },
            "stats": stat_summaries,
            "dependence": dependence,
            "convergence": convergence,
        }

    model_config = {
        "model_version": MODEL_VERSION,
        "empirical_model_version": EMPIRICAL_MODEL_VERSION,
        "scenario_model_version": SCENARIO_MODEL_VERSION,
        "simulation_count": simulation_count,
        "batch_size": batch_size,
        "random_seed": random_seed,
        "joint_sampling_method": "complete_game_joint_empirical_ratio_bootstrap",
        "integerization_method": "independent_stochastic_rounding_after_joint_ratio_scaling",
        "minimum_joint_empirical_games": MIN_JOINT_EMPIRICAL_GAMES,
        "scenario_weights": None,
        "primary_scenario": "base",
        "pra_simulated_independently": False,
        "sportsbook_inputs": False,
    }
    fingerprint_payload = {
        "step_5c_scenario_fingerprint_sha256": scenarios.get("scenario_fingerprint_sha256"),
        "step_5d_distribution_fingerprint_sha256": distribution.get(
            "distribution_fingerprint_sha256"
        ),
        "model_config": model_config,
        "targets": targets,
        "scenario_results": scenario_results,
    }
    simulation_hash = _canonical_hash(fingerprint_payload)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_correlated_monte_carlo_player_outcomes",
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": _utc_now_iso(),
        "simulation_id": f"wnba-5e-{game_id}-{player_id}-{simulation_hash[:16]}",
        "simulation_fingerprint_sha256": simulation_hash,
        "season": distribution.get("season"),
        "season_type": distribution.get("season_type"),
        "game_id": game_id,
        "player_id": player_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "snapshot_reference": deepcopy(distribution.get("snapshot_reference")),
        "step_5c_reference": deepcopy(distribution.get("step_5c_scenario_reference")),
        "step_5d_reference": {
            "model_version": distribution.get("model_version"),
            "distribution_id": distribution.get("distribution_id"),
            "distribution_fingerprint_sha256": distribution.get(
                "distribution_fingerprint_sha256"
            ),
            "selected_game_count": _dig(
                distribution, "distribution_window", "selected_game_count"
            ),
            "selected_game_ids": deepcopy(
                _dig(distribution, "distribution_window", "selected_game_ids")
            ),
        },
        "empirical_basis": {
            "game_count": len(observation_rows),
            "empirical_means": {
                stat: round(float(empirical_means[index]), 8)
                for index, stat in enumerate(STAT_KEYS)
            },
            "joint_rows_sampled_together": True,
            "observed_game_ids": [row["game_id"] for row in observation_rows],
            "method": (
                "Each Monte Carlo trial samples one complete historical P/R/A row, "
                "converts it to ratios around empirical means, and scales all three "
                "ratios to the requested Step-5C scenario target means."
            ),
        },
        "simulation": {
            "requested_simulations": simulation_count,
            "completed_simulations_per_scenario": simulation_count,
            "conditional_scenario_count": len(SCENARIO_KEYS),
            "batch_size": batch_size,
            "batch_count": batch_count,
            "random_seed": random_seed,
            "random_generator": "numpy.random.Generator(PCG64 default_rng)",
            "scenario_weights": None,
            "primary_scenario": "base",
        },
        "conditional_scenario_results": scenario_results,
        "primary_distribution": deepcopy(scenario_results["base"]),
        "convergence": {
            "all_conditional_scenarios_converged": all(convergence_states.values()),
            "by_scenario": convergence_states,
            "numerical_stability_only": True,
        },
        "model_config": model_config,
        "projection_semantics": {
            "base_distribution_centered_on_step_5c_base": True,
            "low_and_high_are_conditional_sensitivity_distributions": True,
            "low_base_high_scenario_probabilities_not_invented": True,
            "p_r_a_sampled_jointly_from_same_empirical_game_row": True,
            "pra_is_exact_simulated_p_plus_r_plus_a": True,
            "observed_empirical_shape_preserved_via_ratio_bootstrap": True,
            "simulation_probabilities_are_model_outputs_not_sportsbook_implied": True,
        },
        "guardrails": {
            "minimum_joint_empirical_sample_required": True,
            "zero_empirical_variance_blocks_correlated_simulation": True,
            "no_multivariate_normal_assumption_required": True,
            "no_independent_pra_simulation": True,
            "no_scenario_mixture_weights_invented": True,
            "no_sportsbook_line_used": True,
            "no_sportsbook_price_used": True,
            "no_betting_edge_created": True,
            "no_ev_created": True,
            "no_named_defender_assignment_inferred": True,
        },
        "verification": {
            "step_5c_model_version_checked": True,
            "step_5d_model_version_checked": True,
            "step_5c_step_5d_identity_checked": True,
            "step_5c_reference_matches_step_5d": True,
            "step_5c_step_5d_snapshot_reference_checked": True,
            "step_5d_observation_means_recomputed": True,
            "step_5d_p_r_a_correlation_basis_recomputed": True,
            "pra_reconstructed_every_trial": True,
            "simulation_count_verified": True,
            "simulation_fingerprint_created": True,
        },
    }


def get_player_game_correlated_monte_carlo(
    player_id: int,
    game_id: str,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    distribution_last_n_games: int = 10,
    simulation_count: int = DEFAULT_SIMULATION_COUNT,
    batch_size: int = DEFAULT_BATCH_SIZE,
    random_seed: int = DEFAULT_RANDOM_SEED,
    require_current_availability: bool = True,
    max_snapshot_age_minutes: int = DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
) -> dict[str, Any]:
    player_id = _positive_player_id(player_id)
    game_id = _game_id(game_id)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _last_n(last_n_games)
    distribution_last_n_games = _distribution_last_n(distribution_last_n_games)
    simulation_count = _simulation_count(simulation_count)
    batch_size = _batch_size(batch_size)
    random_seed = _random_seed(random_seed)
    require_current_availability = _bool(
        require_current_availability, "require_current_availability"
    )
    max_snapshot_age_minutes = _max_snapshot_age(max_snapshot_age_minutes)

    try:
        readiness = get_player_game_model_input_readiness(
            player_id,
            game_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            require_current_availability=require_current_availability,
            include_shot_context=True,
            include_advanced_context=True,
            include_officiating_context=False,
            max_snapshot_age_minutes=max_snapshot_age_minutes,
            include_snapshot=True,
        )
    except WNBAModelInputReadinessNotFoundError as exc:
        raise WNBACorrelatedMonteCarloNotFoundError(str(exc)) from exc
    except WNBAModelInputReadinessUpstreamError as exc:
        raise WNBACorrelatedMonteCarloUpstreamError(str(exc)) from exc

    try:
        scenarios = project_scenarios_from_readiness(readiness)
    except WNBAProjectionScenarioNotReadyError as exc:
        raise WNBACorrelatedMonteCarloNotReadyError(str(exc)) from exc
    except WNBAProjectionScenarioModelInputError as exc:
        raise WNBACorrelatedMonteCarloModelInputError(str(exc)) from exc
    except WNBAProjectionScenarioUpstreamError as exc:
        raise WNBACorrelatedMonteCarloUpstreamError(str(exc)) from exc

    try:
        game_log = get_player_game_log_dataset(
            player_id,
            season,
            season_type=season_type,
        )
    except WNBAHistoryNotFoundError as exc:
        raise WNBACorrelatedMonteCarloNotFoundError(str(exc)) from exc
    except WNBAHistoryUpstreamError as exc:
        raise WNBACorrelatedMonteCarloUpstreamError(str(exc)) from exc

    try:
        distribution = build_empirical_outcome_distribution(
            readiness,
            scenarios,
            game_log,
            season=season,
            season_type=season_type,
            distribution_last_n_games=distribution_last_n_games,
        )
    except WNBAEmpiricalDistributionNotFoundError as exc:
        raise WNBACorrelatedMonteCarloNotFoundError(str(exc)) from exc
    except WNBAEmpiricalDistributionNotReadyError as exc:
        raise WNBACorrelatedMonteCarloNotReadyError(str(exc)) from exc
    except WNBAEmpiricalDistributionModelInputError as exc:
        raise WNBACorrelatedMonteCarloModelInputError(str(exc)) from exc
    except WNBAEmpiricalDistributionUpstreamError as exc:
        raise WNBACorrelatedMonteCarloUpstreamError(str(exc)) from exc

    return simulate_correlated_outcomes(
        scenarios,
        distribution,
        simulation_count=simulation_count,
        batch_size=batch_size,
        random_seed=random_seed,
    )
