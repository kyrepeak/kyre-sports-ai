from __future__ import annotations

import pytest

import cfb_over_under_validation_v1 as validation


def _row(**overrides):
    row = {
        "game_id": "401858213",
        "identity_verified": True,
        "source_mode": "live_shadow",
        "conference": "ACC",
        "market_type": "game_total",
        "model_probability": 0.64,
        "outcome": 1,
        "model_edge_at_signal": 2.5,
        "model_edge_at_close": 1.0,
        "market_total_at_signal": 62.5,
        "market_total_at_close": 63.5,
    }
    row.update(overrides)
    return row


def test_builds_clv_calibration_and_edge_decay_without_projection_influence():
    report = validation.build_validation_report([
        _row(),
        _row(
            game_id="401858214",
            conference="SEC",
            market_type="over",
            model_probability=0.40,
            outcome=0,
            model_edge_at_signal=1.5,
            model_edge_at_close=0.5,
            market_total_at_signal=48.5,
            market_total_at_close=48.0,
        ),
    ])

    overall = report["overall"]
    assert overall["sample_size"] == 2
    assert overall["mean_clv_points"] == pytest.approx(0.25)
    assert overall["mean_signal_edge"] == pytest.approx(2.0)
    assert overall["mean_closing_edge"] == pytest.approx(0.75)
    assert overall["mean_edge_decay"] == pytest.approx(1.25)
    assert overall["brier_score"] == pytest.approx(((0.64 - 1) ** 2 + (0.40 - 0) ** 2) / 2)
    assert report["by_conference"]["ACC"]["sample_size"] == 1
    assert report["by_conference"]["SEC"]["sample_size"] == 1
    assert report["by_market_type"]["game_total"]["sample_size"] == 1
    assert report["by_market_type"]["over"]["sample_size"] == 1
    assert report["diagnostics"]["projection_weight"] == 0.0
    assert report["diagnostics"]["may_modify_projection"] is False
    assert report["diagnostics"]["core_model_frozen"] is True


def test_calibration_curve_is_binned_from_shadow_probabilities():
    report = validation.build_validation_report([
        _row(model_probability=0.64, outcome=1),
        _row(game_id="401858214", model_probability=0.67, outcome=0),
        _row(game_id="401858215", model_probability=0.82, outcome=1),
    ])
    bins = report["calibration_curve"]
    assert len(bins) == 2
    assert bins[0]["sample_size"] == 2
    assert bins[0]["actual_rate"] == pytest.approx(0.5)
    assert bins[1]["sample_size"] == 1
    assert bins[1]["actual_rate"] == pytest.approx(1.0)


def test_non_shadow_rows_fail_closed():
    with pytest.raises(validation.ValidationError, match="unsafe_non_shadow_row:401858213"):
        validation.build_validation_report([_row(source_mode="production_bet")])


def test_non_official_event_ids_fail_closed():
    with pytest.raises(validation.ValidationError, match="unsafe_non_official_event_id:0"):
        validation.build_validation_report([_row(game_id="synthetic-401858213")])


def test_unverified_identity_fails_closed():
    with pytest.raises(validation.ValidationError, match="unsafe_unverified_event_identity:401858213"):
        validation.build_validation_report([_row(identity_verified=False)])


def test_invalid_probability_fails_closed():
    with pytest.raises(validation.ValidationError, match="unsafe_probability:model_probability:401858213"):
        validation.build_validation_report([_row(model_probability=1.01)])


def test_nonfinite_metrics_fail_closed():
    with pytest.raises(validation.ValidationError, match="unsafe_nonfinite:model_edge_at_signal:401858213"):
        validation.build_validation_report([_row(model_edge_at_signal=float("nan"))])


def test_empty_sample_fails_closed():
    with pytest.raises(validation.ValidationError, match="unsafe_empty_validation_sample"):
        validation.build_validation_report([])
