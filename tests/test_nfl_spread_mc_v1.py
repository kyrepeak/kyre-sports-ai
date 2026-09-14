from __future__ import annotations

import inspect
import math

import numpy as np

import nfl_spread_mc_v1 as mc


def _prediction() -> dict:
    return {
        "ready": True,
        "model_version": "NFL SPREAD MODEL V1 TEST",
        "model_quality": "HIGH",
        "game_id": "401872931",
        "projected_away_margin": 2.4,
        "projected_home_margin": -2.4,
        "fair_away_spread": -2.4,
        "fair_home_spread": 2.4,
        "parameter_se": 0.65,
        "residual_sd": 13.25,
        "sportsbook_projection_influence": 0.0,
        "sportsbook_inputs": [],
    }


def _run(
    spread: float | None = None,
    *,
    simulations: int = 120_000,
    seed: int = 20260914,
    batch_size: int = 20_000,
) -> dict:
    return mc.simulate_from_prediction(
        _prediction(),
        spread,
        simulations=simulations,
        seed=seed,
        batch_size=batch_size,
    )


def test_step7c_certified_constants_are_locked() -> None:
    assert mc.CERTIFIED_SIMULATIONS == 5_000_000
    assert mc.DEFAULT_SIMULATIONS == 5_000_000
    assert mc.DEFAULT_BATCH_SIZE == 250_000
    assert mc.DEFAULT_SEED == 20260914
    assert mc.MAX_SIMULATIONS == 10_000_000
    assert mc.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert mc.CERTIFIED_MAX_MC_SE == 0.00025


def test_market_line_is_settlement_only_and_cannot_change_distribution() -> None:
    no_line = _run(None)
    away_minus_three = _run(-3.0)
    away_plus_six = _run(6.0)

    assert no_line["ready"] is True
    assert away_minus_three["ready"] is True
    assert away_plus_six["ready"] is True

    fingerprints = {
        no_line["distribution_fingerprint"],
        away_minus_three["distribution_fingerprint"],
        away_plus_six["distribution_fingerprint"],
    }
    assert len(fingerprints) == 1

    for key in (
        "projected_away_margin",
        "predictive_sd",
        "simulated_away_margin_mean",
        "simulated_away_margin_median",
        "away_win_probability",
        "home_win_probability",
        "tie_probability",
    ):
        assert no_line[key] == away_minus_three[key] == away_plus_six[key]

    assert away_minus_three["market_line_role"] == "settlement_only"
    assert away_minus_three["sportsbook_projection_influence"] == 0.0
    assert away_minus_three["sportsbook_inputs_to_projection"] == []
    assert away_minus_three["away_cover_probability"] != away_plus_six["away_cover_probability"]


def test_same_seed_is_bit_for_bit_reproducible() -> None:
    first = _run(-2.5, simulations=200_000, seed=777, batch_size=25_000)
    second = _run(-2.5, simulations=200_000, seed=777, batch_size=25_000)

    assert first["ready"] is True
    assert second["ready"] is True
    assert first["distribution_fingerprint"] == second["distribution_fingerprint"]
    assert first["margin_distribution"] == second["margin_distribution"]
    assert first["away_cover_probability"] == second["away_cover_probability"]
    assert first["max_batch_cover_probability_diff"] == second["max_batch_cover_probability_diff"]


def test_integer_margin_settlement_supports_real_pushes() -> None:
    whole = _run(-3.0)
    half = _run(-3.5)

    assert whole["push_probability"] > 0.0
    assert half["push_probability"] == 0.0

    assert math.isclose(
        whole["away_cover_probability"]
        + whole["home_cover_probability"]
        + whole["push_probability"],
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    )


def test_distribution_is_normalized_and_margin_keys_are_integers() -> None:
    result = _run()
    distribution = result["margin_distribution"]

    assert result["ready"] is True
    assert math.isclose(sum(distribution.values()), 1.0, rel_tol=0.0, abs_tol=1e-12)
    assert all(str(int(key)) == key for key in distribution)
    assert 0.0 <= result["away_win_probability"] <= 1.0
    assert 0.0 <= result["home_win_probability"] <= 1.0
    assert 0.0 <= result["tie_probability"] <= 1.0


def test_firewall_fails_closed_on_any_projection_market_contamination() -> None:
    contaminated_weight = _prediction()
    contaminated_weight["sportsbook_projection_influence"] = 0.01
    result = mc.simulate_from_prediction(
        contaminated_weight,
        -3.0,
        simulations=20_000,
        batch_size=10_000,
    )
    assert result["ready"] is False
    assert "firewall" in result["error"].lower()

    contaminated_inputs = _prediction()
    contaminated_inputs["sportsbook_inputs"] = ["away_spread"]
    result = mc.simulate_from_prediction(
        contaminated_inputs,
        -3.0,
        simulations=20_000,
        batch_size=10_000,
    )
    assert result["ready"] is False
    assert "firewall" in result["error"].lower()


def test_invalid_prediction_and_runtime_inputs_fail_closed() -> None:
    not_ready = _prediction()
    not_ready["ready"] = False
    not_ready["error"] = "upstream model not ready"
    result = mc.simulate_from_prediction(
        not_ready,
        simulations=20_000,
        batch_size=10_000,
    )
    assert result["ready"] is False
    assert result["error"] == "upstream model not ready"

    bad_sd = _prediction()
    bad_sd["residual_sd"] = np.nan
    result = mc.simulate_from_prediction(
        bad_sd,
        simulations=20_000,
        batch_size=10_000,
    )
    assert result["ready"] is False
    assert "residual_sd" in result["error"]

    too_many = mc.simulate_from_prediction(
        _prediction(),
        simulations=mc.MAX_SIMULATIONS + 1,
        batch_size=10_000,
    )
    assert too_many["ready"] is False
    assert "simulations" in too_many["error"]

    non_dict = mc.simulate_from_prediction(  # type: ignore[arg-type]
        "not-a-prediction",
        simulations=20_000,
        batch_size=10_000,
    )
    assert non_dict["ready"] is False
    assert non_dict["error"] == "margin prediction is not ready"

    malformed_count = mc.simulate_from_prediction(
        _prediction(),
        simulations="five-million",  # type: ignore[arg-type]
        batch_size=10_000,
    )
    assert malformed_count["ready"] is False
    assert "must be integers" in malformed_count["error"]

    malformed_seed = mc.simulate_from_prediction(
        _prediction(),
        simulations=20_000,
        seed=None,  # type: ignore[arg-type]
        batch_size=10_000,
    )
    assert malformed_seed["ready"] is False
    assert "must be integers" in malformed_seed["error"]


def test_source_contract_keeps_projection_inputs_separate_from_market_settlement() -> None:
    source = inspect.getsource(mc.simulate_from_prediction)
    params = inspect.signature(mc.simulate_from_prediction).parameters

    assert "market_away_spread" in params
    assert "sportsbook" not in params
    assert "price" not in params
    assert "odds" not in params
    assert "rng.normal(loc=mean_margin, scale=predictive_sd" in source
    assert source.index("rng.normal(loc=mean_margin, scale=predictive_sd") < source.index(
        "settlement = batch.astype"
    )
    assert "sportsbook_inputs_to_projection" in inspect.getsource(mc._base_result)
    assert "market_line_role" in inspect.getsource(mc._base_result)


def test_real_five_million_run_passes_certification_gate() -> None:
    result = mc.simulate_from_prediction(
        _prediction(),
        -3.0,
        simulations=mc.CERTIFIED_SIMULATIONS,
        seed=mc.DEFAULT_SEED,
        batch_size=mc.DEFAULT_BATCH_SIZE,
    )

    assert result["ready"] is True
    assert result["simulations"] == 5_000_000
    assert result["batches"] == 20
    assert result["converged"] is True
    assert result["certified_run"] is True
    assert result["certification"]["full_5m"] is True
    assert result["certification"]["mc_se_within_limit"] is True
    assert result["certification"]["batch_stability_pass"] is True
    assert result["certification"]["sportsbook_firewall_pass"] is True
    assert result["away_win_mc_se"] <= mc.CERTIFIED_MAX_MC_SE
    assert result["away_cover_mc_se"] <= mc.CERTIFIED_MAX_MC_SE
    assert result["push_mc_se"] <= mc.CERTIFIED_MAX_MC_SE
    assert result["max_batch_win_probability_diff"] <= result["convergence_tolerance"]
    assert result["max_batch_cover_probability_diff"] <= result["convergence_tolerance"]
    assert result["max_batch_push_probability_diff"] <= result["convergence_tolerance"]
