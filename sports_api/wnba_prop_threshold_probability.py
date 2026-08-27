"""Step 5F: WNBA prop threshold probability and fair-odds engine.

Applies a caller-supplied statistical threshold to the already-generated frozen
Step 5E conditional Monte Carlo distributions. The threshold never changes
minutes, projection centers, empirical inputs, Monte Carlo draws, or simulation
configuration.

For integer-valued simulated outcomes:
- Over: simulated value > line
- Under: simulated value < line
- Push: simulated value == line

Fair odds are derived from Over/Under probability conditional on a resolved
(non-push) outcome. No sportsbook price, vig removal, edge, or EV is used.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite, sqrt
from typing import Any

from sports_api.wnba_correlated_monte_carlo import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SIMULATION_COUNT,
    MAX_BATCH_SIZE,
    MAX_SIMULATION_COUNT,
    MIN_BATCH_SIZE,
    MIN_SIMULATION_COUNT,
    MODEL_VERSION as MONTE_CARLO_MODEL_VERSION,
    WNBACorrelatedMonteCarloModelInputError,
    WNBACorrelatedMonteCarloNotFoundError,
    WNBACorrelatedMonteCarloNotReadyError,
    WNBACorrelatedMonteCarloUpstreamError,
    get_player_game_correlated_monte_carlo,
)
from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_model_input_readiness import DEFAULT_MAX_SNAPSHOT_AGE_MINUTES

MODEL_SOURCE = "Kyre Sports API WNBA Step 5F prop threshold probability engine"
MODEL_VERSION = "wnba_step_5f_prop_threshold_probability_v1"
MODEL_FAMILY = "post_projection_monte_carlo_threshold_evaluation"

SUPPORTED_STATS = ("points", "rebounds", "assists", "pra")
STAT_ALIASES = {
    "points": "points",
    "point": "points",
    "pts": "points",
    "rebounds": "rebounds",
    "rebound": "rebounds",
    "reb": "rebounds",
    "rebs": "rebounds",
    "assists": "assists",
    "assist": "assists",
    "ast": "assists",
    "asts": "assists",
    "pra": "pra",
    "points+rebounds+assists": "pra",
    "points rebounds assists": "pra",
}
SCENARIO_KEYS = ("low", "base", "high")
MAX_PROP_LINE = 250.0
MAX_THRESHOLD_MC_STANDARD_ERROR = 0.005
MC_INTERVAL_Z = 1.96
MAX_RECENT_GAMES = 20
MIN_DISTRIBUTION_GAMES = 1
MAX_DISTRIBUTION_GAMES = 50


class WNBAPropThresholdNotReadyError(RuntimeError):
    pass


class WNBAPropThresholdNotFoundError(LookupError):
    pass


class WNBAPropThresholdUpstreamError(RuntimeError):
    pass


class WNBAPropThresholdModelInputError(RuntimeError):
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
    return number if isfinite(number) else None


def _positive_player_id(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _game_id(value: str) -> str:
    result = str(value).strip()
    if len(result) != 10 or not result.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return result


def _stat(value: str) -> str:
    text = " ".join(str(value).strip().casefold().split())
    result = STAT_ALIASES.get(text)
    if result is None:
        raise ValueError(
            "Unsupported WNBA prop stat "
            f"{value!r}. Allowed canonical values: {', '.join(SUPPORTED_STATS)}."
        )
    return result


def _line(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"WNBA prop line must be a number from 0 through {MAX_PROP_LINE:g}.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"WNBA prop line must be a number from 0 through {MAX_PROP_LINE:g}."
        ) from exc
    if not isfinite(number) or not 0.0 <= number <= MAX_PROP_LINE:
        raise ValueError(f"WNBA prop line must be a number from 0 through {MAX_PROP_LINE:g}.")
    return round(number, 6)


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


def _valid_sha256(value: Any) -> bool:
    text = _clean(value)
    return bool(
        text
        and len(text) == 64
        and all(ch in "0123456789abcdefABCDEF" for ch in text)
    )


def _verify_step_5e_fingerprint(monte_carlo: dict[str, Any]) -> None:
    scenario_ref = monte_carlo.get("step_5c_reference")
    distribution_ref = monte_carlo.get("step_5d_reference")
    model_config = monte_carlo.get("model_config")
    scenario_results = monte_carlo.get("conditional_scenario_results")
    if (
        not isinstance(scenario_ref, dict)
        or not isinstance(distribution_ref, dict)
        or not isinstance(model_config, dict)
        or not isinstance(scenario_results, dict)
    ):
        raise WNBAPropThresholdUpstreamError(
            "Step 5E fingerprint source fields are missing."
        )
    scenario_fingerprint = scenario_ref.get("scenario_fingerprint_sha256")
    distribution_fingerprint = distribution_ref.get("distribution_fingerprint_sha256")
    if not _valid_sha256(scenario_fingerprint) or not _valid_sha256(distribution_fingerprint):
        raise WNBAPropThresholdUpstreamError(
            "Step 5E upstream scenario/distribution fingerprints are missing or invalid."
        )
    targets: dict[str, Any] = {}
    for scenario_name in SCENARIO_KEYS:
        row = scenario_results.get(scenario_name)
        target_means = row.get("target_means") if isinstance(row, dict) else None
        if not isinstance(target_means, dict):
            raise WNBAPropThresholdUpstreamError(
                f"Step 5E {scenario_name.upper()} target means are missing."
            )
        targets[scenario_name] = deepcopy(target_means)
    payload = {
        "step_5c_scenario_fingerprint_sha256": scenario_fingerprint,
        "step_5d_distribution_fingerprint_sha256": distribution_fingerprint,
        "model_config": model_config,
        "targets": targets,
        "scenario_results": scenario_results,
    }
    expected = _canonical_hash(payload)
    observed = _clean(monte_carlo.get("simulation_fingerprint_sha256"))
    if observed != expected:
        raise WNBAPropThresholdUpstreamError(
            "Step 5E simulation fingerprint does not match its hash-covered content."
        )


def _validate_monte_carlo(
    monte_carlo: dict[str, Any],
) -> tuple[int, str, str, str, int]:
    if not isinstance(monte_carlo, dict):
        raise ValueError("WNBA Step 5F Monte Carlo payload must be an object.")
    if monte_carlo.get("model_version") != MONTE_CARLO_MODEL_VERSION:
        raise WNBAPropThresholdUpstreamError(
            "Step 5F received an unexpected Step 5E model version."
        )
    if not _valid_sha256(monte_carlo.get("simulation_fingerprint_sha256")):
        raise WNBAPropThresholdUpstreamError(
            "Step 5E simulation fingerprint is missing or invalid."
        )

    player_id = _to_int(monte_carlo.get("player_id"))
    game_id = _clean(monte_carlo.get("game_id"))
    team_key = _clean(monte_carlo.get("team_key"))
    opponent_key = _clean(monte_carlo.get("opponent_team_key"))
    if (
        player_id is None
        or player_id <= 0
        or not game_id
        or len(game_id) != 10
        or not game_id.isdigit()
        or not team_key
        or not opponent_key
        or team_key == opponent_key
    ):
        raise WNBAPropThresholdUpstreamError(
            "Step 5E player/game/team identity is malformed."
        )

    simulation = monte_carlo.get("simulation")
    if not isinstance(simulation, dict):
        raise WNBAPropThresholdUpstreamError(
            "Step 5E simulation metadata is missing."
        )
    simulation_count = _to_int(simulation.get("completed_simulations_per_scenario"))
    requested = _to_int(simulation.get("requested_simulations"))
    if (
        simulation_count is None
        or simulation_count <= 0
        or requested != simulation_count
    ):
        raise WNBAPropThresholdUpstreamError(
            "Step 5E simulation count metadata is inconsistent."
        )
    if _to_int(simulation.get("conditional_scenario_count")) != len(SCENARIO_KEYS):
        raise WNBAPropThresholdUpstreamError(
            "Step 5E conditional scenario count is inconsistent."
        )
    if _clean(simulation.get("primary_scenario")) != "base":
        raise WNBAPropThresholdUpstreamError(
            "Step 5E primary scenario is not BASE."
        )
    if simulation.get("scenario_weights") is not None:
        raise WNBAPropThresholdUpstreamError(
            "Step 5E unexpectedly contains scenario mixture weights."
        )

    scenario_results = monte_carlo.get("conditional_scenario_results")
    if not isinstance(scenario_results, dict):
        raise WNBAPropThresholdUpstreamError(
            "Step 5E conditional scenario results are missing."
        )
    for scenario_name in SCENARIO_KEYS:
        if not isinstance(scenario_results.get(scenario_name), dict):
            raise WNBAPropThresholdUpstreamError(
                f"Step 5E is missing {scenario_name.upper()} conditional results."
            )
    _verify_step_5e_fingerprint(monte_carlo)
    return player_id, game_id, team_key, opponent_key, simulation_count


def _histogram(
    scenario_name: str,
    scenario: dict[str, Any],
    stat: str,
    expected_simulations: int,
) -> tuple[list[tuple[int, int]], dict[str, Any], dict[str, Any]]:
    if _clean(scenario.get("conditional_scenario")) != scenario_name:
        raise WNBAPropThresholdUpstreamError(
            f"Step 5E {scenario_name.upper()} scenario identity is inconsistent."
        )
    stats = scenario.get("stats")
    if not isinstance(stats, dict):
        raise WNBAPropThresholdUpstreamError(
            f"Step 5E {scenario_name.upper()} stat summaries are missing."
        )
    summary = stats.get(stat)
    if not isinstance(summary, dict):
        raise WNBAPropThresholdUpstreamError(
            f"Step 5E {scenario_name.upper()} is missing simulated {stat}."
        )
    if _to_int(summary.get("simulation_count")) != expected_simulations:
        raise WNBAPropThresholdUpstreamError(
            f"Step 5E {scenario_name.upper()} {stat} simulation count is inconsistent."
        )
    rows = summary.get("simulated_distribution")
    if not isinstance(rows, list) or not rows:
        raise WNBAPropThresholdUpstreamError(
            f"Step 5E {scenario_name.upper()} {stat} distribution is missing."
        )

    histogram: list[tuple[int, int]] = []
    seen: set[int] = set()
    previous: int | None = None
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            raise WNBAPropThresholdUpstreamError(
                f"Step 5E {scenario_name.upper()} {stat} distribution contains a malformed row."
            )
        value_raw = row.get("value")
        count_raw = row.get("count")
        if (
            not isinstance(value_raw, int)
            or isinstance(value_raw, bool)
            or value_raw < 0
            or not isinstance(count_raw, int)
            or isinstance(count_raw, bool)
            or count_raw <= 0
        ):
            raise WNBAPropThresholdUpstreamError(
                f"Step 5E {scenario_name.upper()} {stat} histogram contains invalid value/count."
            )
        if value_raw in seen or (previous is not None and value_raw <= previous):
            raise WNBAPropThresholdUpstreamError(
                f"Step 5E {scenario_name.upper()} {stat} histogram values are duplicate or unsorted."
            )
        seen.add(value_raw)
        previous = value_raw
        total += count_raw
        histogram.append((value_raw, count_raw))
    if total != expected_simulations:
        raise WNBAPropThresholdUpstreamError(
            f"Step 5E {scenario_name.upper()} {stat} histogram counts do not equal simulations."
        )

    convergence = scenario.get("convergence")
    if not isinstance(convergence, dict):
        raise WNBAPropThresholdUpstreamError(
            f"Step 5E {scenario_name.upper()} convergence metadata is missing."
        )
    return histogram, summary, convergence


def _probability_record(count: int, total: int) -> dict[str, Any]:
    probability = count / total
    se = sqrt(max(0.0, probability * (1.0 - probability) / total))
    low = max(0.0, probability - MC_INTERVAL_Z * se)
    high = min(1.0, probability + MC_INTERVAL_Z * se)
    return {
        "count": count,
        "probability": round(probability, 10),
        "percentage": round(probability * 100.0, 6),
        "mc_standard_error": round(se, 10),
        "mc_95_interval": {
            "low": round(low, 10),
            "high": round(high, 10),
            "method": "normal_approximation_for_monte_carlo_numerical_error_only",
        },
    }


def _american_odds(probability: float) -> int | None:
    if not 0.0 < probability < 1.0:
        return None
    if abs(probability - 0.5) < 1e-15:
        return 100
    if probability > 0.5:
        return int(round(-100.0 * probability / (1.0 - probability)))
    return int(round(100.0 * (1.0 - probability) / probability))


def _fair_side(probability: float, resolved_count: int) -> dict[str, Any]:
    se = (
        sqrt(max(0.0, probability * (1.0 - probability) / resolved_count))
        if resolved_count > 0
        else None
    )
    if resolved_count <= 0:
        return {
            "available": False,
            "fair_probability": None,
            "fair_percentage": None,
            "resolved_sample_count": 0,
            "mc_standard_error": None,
            "fair_decimal_odds": None,
            "fair_american_odds": None,
            "reason": "all_simulated_outcomes_push_so_no_resolved_fair_odds_exist",
        }
    if probability <= 0.0:
        return {
            "available": False,
            "fair_probability": 0.0,
            "fair_percentage": 0.0,
            "resolved_sample_count": resolved_count,
            "mc_standard_error": round(se, 10) if se is not None else None,
            "fair_decimal_odds": None,
            "fair_american_odds": None,
            "reason": "zero_resolved_win_probability_has_no_finite_fair_payout_odds",
        }
    decimal = 1.0 / probability
    return {
        "available": True,
        "fair_probability": round(probability, 10),
        "fair_percentage": round(probability * 100.0, 6),
        "resolved_sample_count": resolved_count,
        "mc_standard_error": round(se, 10) if se is not None else None,
        "fair_decimal_odds": round(decimal, 6),
        "fair_american_odds": _american_odds(probability),
        "american_odds_note": (
            "American odds are undefined as a finite number at 100% probability."
            if probability >= 1.0
            else None
        ),
    }


def _threshold_scenario(
    scenario_name: str,
    scenario: dict[str, Any],
    stat: str,
    line: float,
    expected_simulations: int,
) -> dict[str, Any]:
    histogram, summary, convergence = _histogram(
        scenario_name, scenario, stat, expected_simulations
    )
    over_count = sum(count for value, count in histogram if value > line)
    under_count = sum(count for value, count in histogram if value < line)
    push_count = expected_simulations - over_count - under_count
    if push_count < 0:
        raise WNBAPropThresholdUpstreamError(
            "Step 5F threshold counts became internally inconsistent."
        )

    over = _probability_record(over_count, expected_simulations)
    under = _probability_record(under_count, expected_simulations)
    push = _probability_record(push_count, expected_simulations)

    resolved_count = over_count + under_count
    if resolved_count > 0:
        resolved_over = over_count / resolved_count
        resolved_under = under_count / resolved_count
    else:
        resolved_over = 0.0
        resolved_under = 0.0

    over_fair = _fair_side(resolved_over, resolved_count)
    under_fair = _fair_side(resolved_under, resolved_count)
    max_se = max(
        over["mc_standard_error"],
        under["mc_standard_error"],
        push["mc_standard_error"],
        over_fair.get("mc_standard_error") or 0.0,
        under_fair.get("mc_standard_error") or 0.0,
    )
    precision_passed = max_se <= MAX_THRESHOLD_MC_STANDARD_ERROR

    return {
        "conditional_scenario": scenario_name,
        "stat": stat,
        "line": line,
        "simulation_count": expected_simulations,
        "settlement": {
            "over_condition": f"{stat} > {line:g}",
            "under_condition": f"{stat} < {line:g}",
            "push_condition": f"{stat} == {line:g}",
            "integer_simulated_outcomes": True,
            "push_possible_for_this_line": float(line).is_integer(),
        },
        "counts": {
            "over": over_count,
            "under": under_count,
            "push": push_count,
            "resolved": resolved_count,
        },
        "raw_probabilities": {
            "over": over,
            "under": under,
            "push": push,
            "sum": round(
                over["probability"] + under["probability"] + push["probability"], 10
            ),
        },
        "fair_odds": {
            "method": "conditional_on_resolved_non_push_outcomes",
            "over": over_fair,
            "under": under_fair,
            "push_probability": push["probability"],
            "resolved_probability_sum": (
                round(resolved_over + resolved_under, 10) if resolved_count else None
            ),
            "semantics": (
                "Pushes return stake under standard two-way player-prop settlement, so "
                "fair Over/Under odds are derived from win probability conditional on "
                "a resolved non-push outcome."
            ),
        },
        "source_distribution_summary": {
            key: deepcopy(summary.get(key))
            for key in (
                "mean",
                "median",
                "modes",
                "minimum",
                "maximum",
                "population_stddev",
                "sample_stddev",
                "mc_standard_error_of_mean",
                "simulated_quantiles",
            )
        },
        "source_convergence": deepcopy(convergence),
        "threshold_precision": {
            "maximum_probability_mc_standard_error": round(max_se, 10),
            "maximum_allowed_probability_mc_standard_error": MAX_THRESHOLD_MC_STANDARD_ERROR,
            "passed": precision_passed,
            "numerical_precision_only": True,
        },
    }


def _favored_side(scenario: dict[str, Any]) -> str:
    fair = scenario["fair_odds"]
    over = fair["over"]
    under = fair["under"]
    if not over.get("available") and not under.get("available"):
        return "unresolved_all_push"
    op = over.get("fair_probability")
    up = under.get("fair_probability")
    if op is None or up is None:
        return "unresolved"
    if abs(op - up) < 1e-12:
        return "balanced"
    return "over" if op > up else "under"


def _scenario_sensitivity(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    raw_over = {
        key: results[key]["raw_probabilities"]["over"]["probability"]
        for key in SCENARIO_KEYS
    }
    raw_under = {
        key: results[key]["raw_probabilities"]["under"]["probability"]
        for key in SCENARIO_KEYS
    }
    resolved_over = {
        key: results[key]["fair_odds"]["over"].get("fair_probability")
        for key in SCENARIO_KEYS
    }
    favored = {key: _favored_side(results[key]) for key in SCENARIO_KEYS}

    valid_resolved = [
        value for value in resolved_over.values() if isinstance(value, (int, float))
    ]
    resolved_span = (
        max(valid_resolved) - min(valid_resolved) if valid_resolved else None
    )
    return {
        "raw_over_probability_by_scenario": raw_over,
        "raw_under_probability_by_scenario": raw_under,
        "raw_over_probability_span": round(max(raw_over.values()) - min(raw_over.values()), 10),
        "raw_over_probability_span_percentage_points": round(
            (max(raw_over.values()) - min(raw_over.values())) * 100.0, 6
        ),
        "resolved_over_fair_probability_by_scenario": resolved_over,
        "resolved_over_fair_probability_span": (
            round(resolved_span, 10) if resolved_span is not None else None
        ),
        "favored_side_by_scenario": favored,
        "same_favored_side_across_all_scenarios": len(set(favored.values())) == 1,
        "base_minus_low_raw_over_probability": round(
            raw_over["base"] - raw_over["low"], 10
        ),
        "high_minus_base_raw_over_probability": round(
            raw_over["high"] - raw_over["base"], 10
        ),
        "semantics": (
            "LOW/BASE/HIGH are conditional scenario sensitivity distributions. "
            "Step 5F does not assign mixture probabilities to those scenarios."
        ),
    }


def evaluate_prop_threshold(
    monte_carlo: dict[str, Any],
    *,
    stat: str,
    line: float,
    require_convergence: bool = True,
) -> dict[str, Any]:
    stat = _stat(stat)
    line = _line(line)
    require_convergence = _bool(require_convergence, "require_convergence")
    player_id, game_id, team_key, opponent_key, simulation_count = _validate_monte_carlo(
        monte_carlo
    )

    raw_scenarios = monte_carlo["conditional_scenario_results"]
    results = {
        scenario_name: _threshold_scenario(
            scenario_name,
            raw_scenarios[scenario_name],
            stat,
            line,
            simulation_count,
        )
        for scenario_name in SCENARIO_KEYS
    }

    convergence_by_scenario = {
        key: results[key]["source_convergence"].get("converged") is True
        for key in SCENARIO_KEYS
    }
    precision_by_scenario = {
        key: results[key]["threshold_precision"]["passed"] is True
        for key in SCENARIO_KEYS
    }
    fair_odds_available_by_scenario = {
        key: results[key]["counts"]["resolved"] > 0
        for key in SCENARIO_KEYS
    }
    all_fair_odds_available = all(fair_odds_available_by_scenario.values())
    all_converged = all(convergence_by_scenario.values())
    all_precise = all(precision_by_scenario.values())
    if require_convergence and not all_converged:
        failed = [key for key, value in convergence_by_scenario.items() if not value]
        raise WNBAPropThresholdNotReadyError(
            "Step 5F requires numerically converged Step 5E conditional scenarios; "
            "not converged: " + ", ".join(failed) + "."
        )
    if require_convergence and not all_precise:
        failed = [key for key, value in precision_by_scenario.items() if not value]
        raise WNBAPropThresholdNotReadyError(
            "Step 5F threshold probability Monte Carlo precision did not pass for: "
            + ", ".join(failed)
            + "."
        )

    sensitivity = _scenario_sensitivity(results)
    model_config = {
        "model_version": MODEL_VERSION,
        "monte_carlo_model_version": MONTE_CARLO_MODEL_VERSION,
        "stat": stat,
        "line": line,
        "require_convergence": require_convergence,
        "fair_odds_method": "conditional_on_resolved_non_push_outcomes",
        "maximum_threshold_mc_standard_error": MAX_THRESHOLD_MC_STANDARD_ERROR,
        "scenario_weights": None,
        "primary_scenario": "base",
        "sportsbook_price_input": False,
    }
    fingerprint_payload = {
        "step_5e_simulation_fingerprint_sha256": monte_carlo.get(
            "simulation_fingerprint_sha256"
        ),
        "model_config": model_config,
        "conditional_threshold_results": results,
        "scenario_sensitivity": sensitivity,
    }
    probability_hash = _canonical_hash(fingerprint_payload)

    simulation_meta = monte_carlo["simulation"]
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_prop_threshold_probability_and_fair_odds",
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": _utc_now_iso(),
        "probability_id": f"wnba-5f-{game_id}-{player_id}-{stat}-{probability_hash[:16]}",
        "probability_fingerprint_sha256": probability_hash,
        "season": monte_carlo.get("season"),
        "season_type": monte_carlo.get("season_type"),
        "game_id": game_id,
        "player_id": player_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "prop": {
            "stat": stat,
            "line": line,
            "line_is_integer": float(line).is_integer(),
            "line_is_threshold_only": True,
            "line_does_not_change_basketball_projection": True,
        },
        "step_5e_reference": {
            "model_version": monte_carlo.get("model_version"),
            "simulation_id": monte_carlo.get("simulation_id"),
            "simulation_fingerprint_sha256": monte_carlo.get(
                "simulation_fingerprint_sha256"
            ),
            "simulation_count_per_scenario": simulation_count,
            "batch_size": simulation_meta.get("batch_size"),
            "batch_count": simulation_meta.get("batch_count"),
            "random_seed": simulation_meta.get("random_seed"),
        },
        "snapshot_reference": deepcopy(monte_carlo.get("snapshot_reference")),
        "step_5c_reference": deepcopy(monte_carlo.get("step_5c_reference")),
        "step_5d_reference": deepcopy(monte_carlo.get("step_5d_reference")),
        "conditional_scenario_results": results,
        "primary_result": deepcopy(results["base"]),
        "scenario_sensitivity": sensitivity,
        "numerical_readiness": {
            "require_convergence": require_convergence,
            "step_5e_converged_by_scenario": convergence_by_scenario,
            "all_step_5e_scenarios_converged": all_converged,
            "threshold_precision_passed_by_scenario": precision_by_scenario,
            "all_threshold_precision_passed": all_precise,
            "fair_odds_available_by_scenario": fair_odds_available_by_scenario,
            "all_fair_odds_available": all_fair_odds_available,
            "strict_numerical_readiness_passed": bool(
                all_converged and all_precise
            ),
            "ready_for_fair_odds": bool(
                all_fair_odds_available
                and ((all_converged and all_precise) or not require_convergence)
            ),
        },
        "model_config": model_config,
        "probability_semantics": {
            "raw_over_under_push_are_monte_carlo_model_probabilities": True,
            "fair_odds_use_resolved_non_push_probability": True,
            "mc_standard_error_is_numerical_simulation_error_only": True,
            "mc_interval_is_not_predictive_confidence_interval": True,
            "low_base_high_are_conditional_scenarios_not_mixture_weights": True,
            "base_is_primary_projection_distribution": True,
        },
        "guardrails": {
            "threshold_applied_after_frozen_step_5e_simulation": True,
            "threshold_cannot_change_projection_means": True,
            "threshold_cannot_change_monte_carlo_draws": True,
            "push_probability_preserved": True,
            "no_scenario_weights_invented": True,
            "no_sportsbook_price_used": True,
            "no_sportsbook_implied_probability_used": True,
            "no_vig_removal_created": True,
            "no_market_edge_created": True,
            "no_ev_created": True,
            "no_named_defender_assignment_inferred": True,
        },
        "verification": {
            "step_5e_model_version_checked": True,
            "step_5e_simulation_fingerprint_checked": True,
            "all_histogram_counts_recomputed": True,
            "all_histogram_counts_equal_simulation_count": True,
            "over_under_push_sum_to_one_checked": True,
            "push_condition_uses_exact_integer_simulated_outcomes": True,
            "fair_odds_condition_on_resolved_outcomes": True,
            "probability_fingerprint_created": True,
        },
    }


def get_player_game_prop_threshold_probability(
    player_id: int,
    game_id: str,
    season: int,
    *,
    stat: str,
    line: float,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    distribution_last_n_games: int = 10,
    simulation_count: int = DEFAULT_SIMULATION_COUNT,
    batch_size: int = DEFAULT_BATCH_SIZE,
    random_seed: int = DEFAULT_RANDOM_SEED,
    require_current_availability: bool = True,
    max_snapshot_age_minutes: int = DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
    require_convergence: bool = True,
) -> dict[str, Any]:
    player_id = _positive_player_id(player_id)
    game_id = _game_id(game_id)
    stat = _stat(stat)
    line = _line(line)
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
    require_convergence = _bool(require_convergence, "require_convergence")

    try:
        monte_carlo = get_player_game_correlated_monte_carlo(
            player_id,
            game_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            distribution_last_n_games=distribution_last_n_games,
            simulation_count=simulation_count,
            batch_size=batch_size,
            random_seed=random_seed,
            require_current_availability=require_current_availability,
            max_snapshot_age_minutes=max_snapshot_age_minutes,
        )
    except WNBACorrelatedMonteCarloNotFoundError as exc:
        raise WNBAPropThresholdNotFoundError(str(exc)) from exc
    except WNBACorrelatedMonteCarloNotReadyError as exc:
        raise WNBAPropThresholdNotReadyError(str(exc)) from exc
    except WNBACorrelatedMonteCarloModelInputError as exc:
        raise WNBAPropThresholdModelInputError(str(exc)) from exc
    except WNBACorrelatedMonteCarloUpstreamError as exc:
        raise WNBAPropThresholdUpstreamError(str(exc)) from exc

    return evaluate_prop_threshold(
        monte_carlo,
        stat=stat,
        line=line,
        require_convergence=require_convergence,
    )
