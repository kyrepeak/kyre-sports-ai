from __future__ import annotations

import inspect
import math

import numpy as np

import nfl_spread_model_v1 as model


def test_model_constants_lock_market_independence() -> None:
    assert model.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert model.CALIBRATION_SEASONS == (2024, 2025)
    assert model.HOLDOUT_SEASON == 2025
    assert model.FEATURE_NAMES == (
        "strength_gap",
        "scoring_gap",
        "recent_gap",
        "site_sign",
    )


def test_ridge_fit_returns_finite_coefficients_covariance_and_residuals() -> None:
    rng = np.random.default_rng(20260914)
    x = rng.normal(size=(500, 4))
    truth = np.array([2.0, -1.25, 0.75, 1.5])
    y = x @ truth + rng.normal(0.0, 3.0, size=500)
    scales = np.ones(4, dtype=float)

    beta, covariance, residuals, residual_sd = model._fit_ridge_linear(
        x, y, scales
    )

    assert beta.shape == (4,)
    assert covariance.shape == (4, 4)
    assert residuals.shape == (500,)
    assert np.all(np.isfinite(beta))
    assert np.all(np.isfinite(covariance))
    assert np.all(np.isfinite(residuals))
    assert math.isfinite(residual_sd)
    assert residual_sd > 0.0


def test_prediction_math_and_fair_spread_sign_are_locked(monkeypatch) -> None:
    feature_vector = np.array([1.0, 2.0, -1.0, 1.0], dtype=float)
    fitted = {
        "ready": True,
        "quality": "HIGH",
        "beta": np.array([2.0, 1.0, -0.5, 1.5], dtype=float),
        "scales": np.ones(4, dtype=float),
        "covariance": np.eye(4, dtype=float) * 0.04,
        "residual_sd": 13.0,
        "sportsbook_projection_influence": 0.0,
        "sportsbook_inputs": [],
    }

    monkeypatch.setattr(
        model,
        "current_game_feature",
        lambda game, day_str: {
            "ready": True,
            "game_id": "401872931",
            "x": feature_vector,
            "feature": {"ready": True},
            "away_profile_quality": "HIGH",
            "home_profile_quality": "HIGH",
            "site_provider_ok": True,
            "sportsbook_projection_influence": 0.0,
        },
    )

    result = model.predict_game_margin(
        {"game_id": "401872931"},
        "2026-09-14",
        fitted=fitted,
    )

    expected_margin = 6.0
    expected_parameter_se = math.sqrt(0.04 * float(feature_vector @ feature_vector))

    assert result["ready"] is True
    assert result["projected_away_margin"] == expected_margin
    assert result["projected_home_margin"] == -expected_margin
    assert result["fair_away_spread"] == -expected_margin
    assert result["fair_home_spread"] == expected_margin
    assert math.isclose(
        result["parameter_se"], expected_parameter_se, rel_tol=0.0, abs_tol=1e-12
    )
    assert result["residual_sd"] == 13.0
    assert result["sportsbook_projection_influence"] == 0.0
    assert result["sportsbook_inputs"] == []


def test_prediction_fails_closed_when_upstream_model_is_not_ready() -> None:
    result = model.predict_game_margin(
        {"game_id": "401872931"},
        "2026-09-14",
        fitted={
            "ready": False,
            "quality": "LOW",
            "error": "validation guard failed",
        },
    )

    assert result["ready"] is False
    assert result["model_quality"] == "LOW"
    assert result["error"] == "validation guard failed"
    assert result["sportsbook_projection_influence"] == 0.0


def test_model_source_does_not_import_spread_market_transport() -> None:
    source = inspect.getsource(model)

    assert "import nfl_spread_market_api_v1" not in source
    assert "from nfl_spread_market_api_v1" not in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert '"sportsbook_inputs": []' in source
