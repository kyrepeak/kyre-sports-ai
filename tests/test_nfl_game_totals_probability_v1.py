import math

import pytest

import sports_api.nfl_game_totals_probability_v1 as probability


PROJECTION = {
    "ready": True,
    "model_version": "NFL GAME TOTALS PROJECTION V1 • FOOTBALL-ONLY SCORING INTERACTION",
    "official_event_id": "401772714",
    "away_team_id": "8",
    "home_team_id": "2",
    "projected_away_points": 24.0,
    "projected_home_points": 25.1875,
    "projected_total": 49.1875,
    "football_only": True,
    "sportsbook_projection_influence": 0.0,
    "sportsbook_inputs": [],
    "market_total_used": False,
}


def test_probability_contract_freezes_certified_simulation_settings():
    assert probability.CERTIFIED_SIMULATIONS == 5_000_000
    assert probability.CERTIFIED_BATCHES == 20
    assert isinstance(probability.CERTIFIED_SEED, int)
    assert probability.SPORTSBOOK_DISTRIBUTION_INFLUENCE == 0.0
    assert probability.TEAM_SCORE_CORRELATION >= 0.0
    assert probability.TEAM_SCORE_CORRELATION < 1.0


def test_half_point_line_has_no_push_and_probabilities_sum_to_one():
    out = probability.simulate_over_under(
        PROJECTION,
        49.5,
        simulations=200_000,
        batches=10,
        seed=12345,
    )
    assert out["push_probability"] == 0.0
    assert out["over_probability"] + out["under_probability"] == pytest.approx(1.0)
    assert out["over_probability"] + out["under_probability"] + out["push_probability"] == pytest.approx(1.0)
    assert out["simulation"]["simulations"] == 200_000
    assert out["simulation"]["batches"] == 10
    assert out["simulation"]["seed"] == 12345


def test_integer_line_can_produce_push_probability():
    out = probability.simulate_over_under(
        PROJECTION,
        49.0,
        simulations=250_000,
        batches=10,
        seed=12345,
    )
    assert out["push_probability"] > 0.0
    assert out["over_probability"] + out["under_probability"] + out["push_probability"] == pytest.approx(1.0)


def test_same_seed_is_deterministic():
    first = probability.simulate_over_under(PROJECTION, 49.5, simulations=120_000, batches=6, seed=991)
    second = probability.simulate_over_under(PROJECTION, 49.5, simulations=120_000, batches=6, seed=991)
    assert first == second


def test_market_line_is_threshold_only_and_does_not_change_distribution():
    low = probability.simulate_over_under(PROJECTION, 45.5, simulations=150_000, batches=10, seed=2026)
    high = probability.simulate_over_under(PROJECTION, 53.5, simulations=150_000, batches=10, seed=2026)
    assert low["simulated_mean"] == high["simulated_mean"]
    assert low["median"] == high["median"]
    assert low["p10"] == high["p10"]
    assert low["p90"] == high["p90"]
    assert low["over_probability"] > high["over_probability"]
    assert low["market_line_influence_on_distribution"] == 0.0
    assert high["market_line_influence_on_distribution"] == 0.0


def test_fair_odds_use_no_push_probability():
    out = probability.simulate_over_under(PROJECTION, 49.0, simulations=200_000, batches=10, seed=77)
    fair = out["fair_odds"]
    assert 0.0 < fair["over_no_push_probability"] < 1.0
    assert 0.0 < fair["under_no_push_probability"] < 1.0
    assert fair["over_no_push_probability"] + fair["under_no_push_probability"] == pytest.approx(1.0)
    assert isinstance(fair["over_american"], int)
    assert isinstance(fair["under_american"], int)


def test_certified_five_million_run_reports_stability_and_convergence():
    out = probability.simulate_over_under(
        PROJECTION,
        49.5,
        simulations=probability.CERTIFIED_SIMULATIONS,
        batches=probability.CERTIFIED_BATCHES,
        seed=probability.CERTIFIED_SEED,
    )
    sim = out["simulation"]
    assert sim["simulations"] == 5_000_000
    assert sim["batches"] == 20
    assert sim["monte_carlo_se"] < 0.001
    assert sim["max_batch_over_probability_difference"] < 0.01
    assert sim["converged"] is True
    assert math.isfinite(out["simulated_mean"])
    assert out["p10"] <= out["median"] <= out["p90"]


def test_probability_engine_rejects_market_contaminated_projection():
    contaminated = dict(PROJECTION)
    contaminated["sportsbook_inputs"] = ["total"]
    with pytest.raises(probability.NFLGameTotalsProbabilityError):
        probability.simulate_over_under(contaminated, 49.5, simulations=10_000, batches=2, seed=1)


def test_probability_engine_rejects_invalid_line_or_simulation_shape():
    with pytest.raises(probability.NFLGameTotalsProbabilityError):
        probability.simulate_over_under(PROJECTION, float("nan"), simulations=10_000, batches=2, seed=1)
    with pytest.raises(probability.NFLGameTotalsProbabilityError):
        probability.simulate_over_under(PROJECTION, 49.5, simulations=10_001, batches=2, seed=1)
