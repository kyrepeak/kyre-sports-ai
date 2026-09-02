"""OFF-only live certification for Step-8D 5,000,000-draw joint Monte Carlo."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from typing import Any

from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector
from sports_api.wnba_step8_joint_monte_carlo import (
    CERTIFIED_MAX_BATCH_PROBABILITY_RANGE,
    CERTIFIED_MAX_MEAN_TARGET_ERROR,
    CERTIFIED_MAX_MONTE_CARLO_SE,
    DEFAULT_BATCH_SIZE,
    DEFAULT_SIMULATIONS,
    MODEL_VERSION,
    SCHEMA_VERSION,
    get_player_game_step8_joint_probability_distribution,
    step8_monte_carlo_enabled,
)

REPORT_PATH = Path("step8d-joint-monte-carlo-cert.json")
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


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _assert_safe() -> None:
    bad = [key for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))]
    if bad:
        raise RuntimeError("Step 8D cert refuses production switches: " + ", ".join(bad))
    for key in (
        "WNBA_STEP7G_FIRST_PARTY_ENABLED",
        "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED",
        "WNBA_STEP8_CORE_PROJECTION_ENABLED",
        "WNBA_STEP8_CONTEXT_ADJUSTMENT_ENABLED",
        "WNBA_STEP8_MONTE_CARLO_ENABLED",
    ):
        if not _truthy(os.getenv(key)):
            raise RuntimeError(f"Step 8D cert requires isolated flag {key}=true.")
    if not step8_monte_carlo_enabled():
        raise RuntimeError("Step 8D Monte Carlo flag is not enabled in isolated CI.")


def _num(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"Step 8D cert expected numeric {label}.")
    result = float(value)
    if not math.isfinite(result):
        raise RuntimeError(f"Step 8D cert expected finite {label}.")
    return result


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    selector.MIN_TIP_BUFFER_HOURS = 0.5
    game, player, _ = selector._select_live_pregame_case()
    game_id = str(game["game_id"])
    player_id = int(player["player_id"])

    result = get_player_game_step8_joint_probability_distribution(
        player_id,
        game_id,
        simulations=DEFAULT_SIMULATIONS,
        batch_size=DEFAULT_BATCH_SIZE,
    )
    if result.get("data_type") != "joint_player_stat_probability_distribution":
        raise RuntimeError("Step 8D returned the wrong data type.")
    if result.get("schema_version") != SCHEMA_VERSION or result.get("model_version") != MODEL_VERSION:
        raise RuntimeError("Step 8D returned the wrong schema/model version.")
    if result.get("game_id") != game_id or result.get("player_id") != player_id:
        raise RuntimeError("Step 8D returned the wrong requested identity.")

    simulation = result.get("simulation") or {}
    if simulation.get("simulations") != DEFAULT_SIMULATIONS:
        raise RuntimeError("Step 8D did not execute exactly 5,000,000 simulations.")
    expected_batches = math.ceil(DEFAULT_SIMULATIONS / DEFAULT_BATCH_SIZE)
    if simulation.get("batch_size") != DEFAULT_BATCH_SIZE or simulation.get("batch_count") != expected_batches:
        raise RuntimeError("Step 8D simulation batching does not match the certified configuration.")
    if not isinstance(simulation.get("random_seed"), int):
        raise RuntimeError("Step 8D did not expose a deterministic random seed.")

    target = result.get("step8c_target") or {}
    distributions = result.get("distributions") or {}
    for stat in (*_STATS, _PRA):
        distribution = distributions.get(stat)
        if not isinstance(distribution, dict):
            raise RuntimeError(f"Step 8D is missing the {stat} distribution.")
        if abs(_num(distribution.get("probability_mass_sum"), f"{stat} mass sum") - 1.0) > 1e-10:
            raise RuntimeError(f"Step 8D {stat} probability mass does not sum to 1.")
        expected = _num(distribution.get("expected"), f"{stat} expected")
        target_mean = _num(target.get(stat), f"{stat} target")
        if abs(expected - target_mean) > CERTIFIED_MAX_MEAN_TARGET_ERROR:
            raise RuntimeError(f"Step 8D {stat} simulation mean drifted too far from Step 8C.")
        if not isinstance(distribution.get("median"), int) or not isinstance(distribution.get("mode"), int):
            raise RuntimeError(f"Step 8D {stat} median/mode is not discrete.")
        if not isinstance(distribution.get("probability_mass"), list) or not distribution["probability_mass"]:
            raise RuntimeError(f"Step 8D {stat} probability mass table is missing.")

    component_expected = sum(_num(distributions[stat]["expected"], stat) for stat in _STATS)
    pra_expected = _num(distributions[_PRA]["expected"], "PRA expected")
    if abs(component_expected - pra_expected) > 2e-6:
        raise RuntimeError("Step 8D PRA distribution was not recomposed from the same P/R/A draws.")

    model = result.get("model_specification") or {}
    if model.get("family") != "regularized_gaussian_copula_discrete_counts":
        raise RuntimeError("Step 8D joint model family is not locked.")
    if model.get("sample_game_count") != 5:
        raise RuntimeError("Step 8D did not use the exact five-game official evidence window.")
    weight = _num(model.get("empirical_evidence_weight"), "empirical evidence weight")
    if abs(weight - 0.25) > 1e-12:
        raise RuntimeError("Step 8D five-game covariance regularization weight is not 0.25.")
    empirical = model.get("empirical_correlation") or {}
    regularized = model.get("regularized_latent_correlation") or {}
    for left in _STATS:
        for right in _STATS:
            empirical_value = _num((empirical.get(left) or {}).get(right), f"empirical {left}/{right}")
            regularized_value = _num((regularized.get(left) or {}).get(right), f"regularized {left}/{right}")
            expected_value = 1.0 if left == right else weight * empirical_value
            if abs(regularized_value - expected_value) > 2e-8:
                raise RuntimeError("Step 8D regularized correlation does not reproduce the locked shrinkage formula.")
    eigenvalues = model.get("regularized_correlation_eigenvalues")
    if not isinstance(eigenvalues, list) or len(eigenvalues) != 3 or min(_num(v, "correlation eigenvalue") for v in eigenvalues) <= 0:
        raise RuntimeError("Step 8D regularized correlation matrix is not positive definite.")

    marginals = model.get("marginals") or {}
    for stat in _STATS:
        marginal = marginals.get(stat) or {}
        if marginal.get("family") not in {"poisson", "negative_binomial", "binomial"}:
            raise RuntimeError(f"Step 8D {stat} marginal family is not supported.")
        if _num(marginal.get("regularized_variance_to_mean"), f"{stat} variance/mean") <= 0:
            raise RuntimeError(f"Step 8D {stat} regularized dispersion is invalid.")

    examples = result.get("example_half_point_lines_near_target") or {}
    for stat in (*_STATS, _PRA):
        row = examples.get(stat) or {}
        total = sum(_num(row.get(key), f"{stat} {key}") for key in ("under_probability", "push_probability", "over_probability"))
        if abs(total - 1.0) > 2e-8 or _num(row.get("push_probability"), f"{stat} push") != 0.0:
            raise RuntimeError(f"Step 8D half-point probability example is inconsistent for {stat}.")

    convergence = result.get("convergence") or {}
    if convergence.get("converged") is not True:
        raise RuntimeError("Step 8D 5,000,000-draw run did not meet convergence certification.")
    if _num(convergence.get("max_probe_batch_probability_range"), "max batch range") > CERTIFIED_MAX_BATCH_PROBABILITY_RANGE:
        raise RuntimeError("Step 8D batch probability stability exceeded the certification limit.")
    if _num(convergence.get("max_mean_target_absolute_error"), "max mean error") > CERTIFIED_MAX_MEAN_TARGET_ERROR:
        raise RuntimeError("Step 8D mean calibration exceeded the certification limit.")
    if _num(convergence.get("max_probe_monte_carlo_standard_error"), "max MC SE") > CERTIFIED_MAX_MONTE_CARLO_SE:
        raise RuntimeError("Step 8D Monte Carlo standard error exceeded the certification limit.")

    guardrails = result.get("guardrails") or {}
    for key in (
        "official_integer_box_counts_only_for_dispersion_and_dependence",
        "small_sample_variance_regularized_toward_poisson",
        "small_sample_correlation_regularized_toward_independence",
        "p_r_a_not_simulated_independently",
        "pra_recomposed_from_same_joint_p_r_a_draws",
    ):
        if guardrails.get(key) is not True:
            raise RuntimeError(f"Step 8D guardrail {key!r} is not true.")
    for key in ("sportsbook_data_used", "supabase_mutated", "persistence_mutated", "scheduler_enabled"):
        if guardrails.get(key) is not False:
            raise RuntimeError(f"Step 8D unexpectedly enabled/mutated {key!r}.")
    if guardrails.get("production_activation_allowed") is not False:
        raise RuntimeError("Step 8D unexpectedly permits production activation.")

    report = {
        "data_type": "wnba_step8d_joint_monte_carlo_cert_v1",
        "certification_result": "STEP8D_5M_JOINT_MONTE_CARLO_LIVE_CERTIFIED",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_game": game,
        "selected_player": player,
        "result_content_sha256": result.get("result_content_sha256"),
        "model_version": result.get("model_version"),
        "step8c_target": target,
        "simulation": simulation,
        "model_specification": model,
        "distribution_summary": {
            stat: {
                key: distributions[stat].get(key)
                for key in ("expected", "stddev", "median", "mode", "quantiles")
            }
            for stat in (*_STATS, _PRA)
        },
        "example_half_point_lines_near_target": examples,
        "achieved_joint_dependence": result.get("achieved_joint_dependence"),
        "convergence": convergence,
        "safety": {
            "joint_probability_distribution_created": True,
            "simulations": DEFAULT_SIMULATIONS,
            "sportsbook_called": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_enabled": False,
            "production_runtime_enabled": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("STEP8D_5M_JOINT_MONTE_CARLO_LIVE_CERTIFIED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
