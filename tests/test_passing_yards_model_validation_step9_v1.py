from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import nfl_passing_yards_context_v1 as context
import nfl_passing_yards_distribution_v1 as distribution
import nfl_passing_yards_market_v1 as market
import nfl_passing_yards_projection_v1 as projection


ROOT = Path(__file__).resolve().parents[1]


def _inputs():
    qb_ctx = {"qb1": {"athlete_id": "999", "name": "Validated QB"}}
    qb_profile = {
        "ready": True,
        "athlete_id": "999",
        "qb_name": "Validated QB",
        "season": {"attempts_per_game": 35.0, "yards_per_attempt": 8.0},
        "recent3_attempts": 40.0,
        "recent3_yards": 300.0,
        "recent_games": [
            {"passing_yards": 310.0},
            {"passing_yards": 280.0},
            {"passing_yards": 255.0},
            {"passing_yards": 295.0},
            {"passing_yards": 265.0},
        ],
    }
    defense = {
        "ready": True,
        "team_id": "34",
        "team_name": "Opponent",
        "season": {
            "passing_attempts_allowed_per_game": 38.0,
            "yards_per_attempt_allowed": 7.0,
        },
        "recent3_ypa_allowed": 6.8,
    }
    pressure = {
        "ready": True,
        "pressure_label": "MODERATE",
        "offense": {"sack_rate_allowed": 6.0},
        "defense": {"sack_rate_generated": 10.0},
    }
    personnel = {"qb_status": "No listed injury", "personnel_label": "NEUTRAL"}
    environment = {
        "away_pace": {"pass_attempts_per_game": 37.0},
        "away_rest": {"turnaround_days": 7, "rest_label": "STANDARD"},
        "environment_label": "NEUTRAL",
        "weather_label": "NORMAL",
    }
    return qb_ctx, qb_profile, defense, pressure, personnel, environment


def _chain():
    qb_ctx, qb_profile, defense, pressure, personnel, environment = _inputs()
    step7 = projection.build_baseline_projection(
        qb_ctx, qb_profile, defense, pressure, personnel, environment,
        side="away", preseason=False,
    )
    step8 = context.build_context_projection(
        step7, qb_profile, pressure, personnel, environment,
        side="away", preseason=False,
    )
    step9 = distribution.build_distribution(step8)
    return step7, step8, step9


def test_step9_model_validation_recomputes_from_football_inputs() -> None:
    step7, step8, step9 = _chain()

    manual_attempts = (
        35.0 * projection.ATTEMPT_WEIGHTS["qb_season_attempts_per_game"]
        + 40.0 * projection.ATTEMPT_WEIGHTS["qb_recent3_attempts"]
        + 38.0 * projection.ATTEMPT_WEIGHTS["opponent_attempts_allowed_per_game"]
        + 37.0 * projection.ATTEMPT_WEIGHTS["team_pass_attempts_per_game"]
    )
    manual_ypa = (
        8.0 * projection.YPA_WEIGHTS["qb_season_ypa"]
        + (300.0 / 40.0) * projection.YPA_WEIGHTS["qb_recent3_ypa"]
        + 7.0 * projection.YPA_WEIGHTS["opponent_season_ypa_allowed"]
        + 6.8 * projection.YPA_WEIGHTS["opponent_recent3_ypa_allowed"]
    )
    manual_baseline = manual_attempts * manual_ypa

    assert abs(sum(projection.ATTEMPT_WEIGHTS.values()) - 1.0) < 1e-12
    assert abs(sum(projection.YPA_WEIGHTS.values()) - 1.0) < 1e-12
    assert step7["ready"] is True
    assert abs(step7["expected_attempts"] - manual_attempts) < 1e-12
    assert abs(step7["expected_ypa"] - manual_ypa) < 1e-12
    assert abs(step7["projection_yards"] - manual_baseline) < 1e-9

    expected_pressure_delta = -(
        manual_attempts * (((6.0 + 10.0) / 2.0) - 6.0) / 100.0
    ) * manual_ypa
    assert step8["ready"] is True
    assert abs(step8["pressure_adjustment_yards"] - expected_pressure_delta) < 1e-9
    assert abs(step8["context_projection_yards"] - (manual_baseline + expected_pressure_delta)) < 1e-9

    assert step9["ready"] is True
    assert step9["location_yards"] == step8["context_projection_yards"]
    assert step9["sigma_yards"] > 0.0
    assert step9["probability_enabled"] is True


def test_step9_validation_proves_sportsbook_cannot_feed_back_into_model() -> None:
    step7, step8, step9 = _chain()
    frozen = deepcopy(step9)

    market_a = market.evaluate_market(
        step9, 249.5, -110, -110, source="validation-a", market_timestamp="2026-09-24T00:00:00Z"
    )
    market_b = market.evaluate_market(
        step9, 299.5, +105, -125, source="validation-b", market_timestamp="2026-09-24T00:01:00Z"
    )

    assert step9 == frozen
    assert step7["sportsbook_influence"] == 0.0
    assert step8["sportsbook_influence"] == 0.0
    assert step9["sportsbook_influence"] == 0.0
    for result in (market_a, market_b):
        assert result["ready"] is True
        assert result["sportsbook_projection_influence"] == 0.0
        assert result["projection_adjustment_yards"] == 0.0
        assert result["stake_sizing_enabled"] is False


def test_step9_distribution_invariants_hold() -> None:
    _, _, step9 = _chain()
    rows = step9["thresholds"]
    overs = [row["over_probability"] for row in rows]

    assert all(0.0 <= p <= 1.0 for p in overs)
    assert overs == sorted(overs, reverse=True)
    for row in rows:
        assert abs(row["over_probability"] + row["under_probability"] - 1.0) < 1e-12

    quantiles = [step9["quantiles"][key] for key in ("p10", "p25", "p50", "p75", "p90")]
    assert quantiles == sorted(quantiles)
    assert min(quantiles) >= 0.0
    assert step9["monte_carlo_enabled"] is False
    assert step9["simulation_count"] == 0
    assert step9["fair_odds_enabled"] is False
    assert step9["ev_enabled"] is False
    assert step9["ranking_enabled"] is False
    assert step9["recommendation_enabled"] is False


def test_step9_is_verifier_only_and_preserves_step8_product_owners() -> None:
    workflow = (ROOT / ".github/workflows/passing-yards-model-validation-step9-v1.yml").read_text()
    assert "MODEL_VALIDATION_STEP9" in workflow
    assert "nfl_passing_yards_hub_v78.py" not in workflow
    assert "streamlit_memory_lazy_router_v229.py" not in workflow
