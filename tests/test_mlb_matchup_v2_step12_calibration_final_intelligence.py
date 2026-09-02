from __future__ import annotations

import inspect

import pandas as pd
import pytest

import mlb_matchup_calibration_v1 as calibration
import mlb_matchup_hub_v27 as router
import mlb_matchup_hub_v41 as hub
import mlb_matchup_player_v35 as player


def _raw_profile(**overrides):
    distribution = {0: 0.35, 1: 0.40, 2: 0.18, 3: 0.06, 4: 0.01}
    row = {
        "probability_status": "READY_RAW",
        "game_pk": 999001,
        "game_date": "2099-09-02",
        "game_status": "Scheduled",
        "player_id": 123,
        "player_name": "Test Hitter",
        "team": "AAA",
        "opponent": "BBB",
        "starter_name": "Test Starter",
        "slot": 2,
        "confirmed": True,
        "projected": False,
        "composite_data_score": 82.0,
        "base_hit_per_pa": 0.20,
        "starter_pa": 2.50,
        "bullpen_pa": 1.50,
        "expected_pa": 4.0,
        "p0": 0.35,
        "p1_plus": 0.65,
        "p2_plus": 0.25,
        "p_exactly_1": 0.40,
        "expected_hits": 0.98,
        "monte_carlo_distribution": distribution,
        "starter_probability_sigma": 0.18,
        "bullpen_probability_sigma": 0.20,
        "monte_carlo_converged": True,
        "simulations": 5_000_000,
        "batches": 20,
        "random_seed": 110011,
        "mc_se_p1_plus": 0.0002,
    }
    row.update(overrides)
    return row


def _graded_rows(n: int, probability: float, actual_rate: float, model_version: str | None = None):
    hits = int(round(n * actual_rate))
    rows = []
    for i in range(n):
        actual = 1 if i < hits else 0
        rows.append(
            {
                "model_version": model_version or calibration.RAW_MODEL_VERSION,
                "grade_status": "GRADED",
                "predicted_p1": probability,
                "predicted_p2": max(0.05, probability - 0.35),
                "predicted_p3": max(0.02, probability - 0.52),
                "actual_hits": 2 if actual and i % 3 == 0 else 1 if actual else 0,
                "actual_1plus": actual,
            }
        )
    return rows


def test_step12_constants_and_final_probability_boundary():
    assert player.PROBABILITY_IMPACT == "ACTIVE_FINAL_V2"
    assert player.STEP12_ROLE == "CALIBRATION_FINAL_INTELLIGENCE"
    assert calibration.RAW_MODEL_VERSION == "MLB_MATCHUP_V2_STEP11_RAW"
    assert calibration.MIN_BACKTEST_GAMES == 30
    assert calibration.STRONG_BACKTEST_GAMES == 100
    assert calibration.MATURE_BACKTEST_GAMES == 250


def test_fair_odds_math():
    assert calibration.american_fair_odds(0.50) == -100
    assert calibration.american_fair_odds(0.60) == -150
    assert calibration.american_fair_odds(0.40) == 150
    assert calibration.american_fair_odds(None) is None


def test_prediction_record_uses_exact_v2_raw_model_version():
    record = calibration.prediction_record(_raw_profile())
    assert record is not None
    assert record["model_version"] == calibration.RAW_MODEL_VERSION
    assert record["prediction_key"].endswith(calibration.RAW_MODEL_VERSION)
    assert record["predicted_p1"] == pytest.approx(0.65)
    assert record["predicted_p2"] == pytest.approx(0.25)
    assert record["predicted_p3"] == pytest.approx(0.07)


def test_v2_history_filter_never_borrows_frozen_v1_records():
    rows = _graded_rows(5, 0.70, 0.60)
    rows += _graded_rows(7, 0.80, 0.75, model_version="V13")
    filtered = calibration.load_v2_graded_history(pd.DataFrame(rows))
    assert len(filtered) == 5
    assert set(filtered["model_version"]) == {calibration.RAW_MODEL_VERSION}


def test_cold_start_does_not_fabricate_empirical_correction():
    records = pd.DataFrame(_graded_rows(29, 0.70, 0.40))
    fit = calibration.fit_empirical_calibrator(records, 1)
    assert fit["status"] == "COLD_START"
    assert fit["n"] == 29
    assert calibration.apply_empirical_calibrator(0.72, fit) == pytest.approx(0.72)


def test_warmup_global_correction_is_bounded():
    records = pd.DataFrame(_graded_rows(60, 0.70, 0.50))
    fit = calibration.fit_empirical_calibrator(records, 1)
    assert fit["status"] == "WARMUP"
    assert fit["global_gap"] == pytest.approx(-calibration.MAX_GLOBAL_CALIBRATION_SHIFT)
    assert calibration.apply_empirical_calibrator(0.70, fit) == pytest.approx(0.64)


def test_empirical_bin_anchors_are_monotone_after_pav():
    rows = []
    specs = [(0.60, 0.80), (0.70, 0.45), (0.80, 0.90)]
    for probability, actual_rate in specs:
        rows.extend(_graded_rows(40, probability, actual_rate))
    fit = calibration.fit_empirical_calibrator(pd.DataFrame(rows), 1)
    assert fit["status"] == "STRONG"
    assert len(fit["anchors"]) >= 3
    ys = [row["y"] for row in fit["anchors"]]
    assert ys == sorted(ys)


def test_reliability_weight_penalizes_weak_or_projected_inputs():
    strong = calibration.reliability_weight(_raw_profile(composite_data_score=95, confirmed=True, projected=False))
    weak = calibration.reliability_weight(_raw_profile(composite_data_score=50, confirmed=False, projected=True, probability_status="PROVISIONAL_RAW"))
    assert strong["weight"] > weak["weight"]
    assert weak["missing_data_penalty"] > strong["missing_data_penalty"]
    assert 0.45 <= weak["weight"] <= 1.0


def test_final_cold_start_shrinks_raw_probability_toward_neutral():
    raw = _raw_profile()
    final = calibration.build_final_intelligence(raw, backtest_records=pd.DataFrame(), persist=False)
    assert final["final_status"] == "FINAL_PROVISIONAL_COLD_START"
    assert final["calibration_status_step12"] == "COLD_START"
    assert final["empirical_p1_plus"] == pytest.approx(raw["p1_plus"])
    neutral = final["neutral_p1_plus"]
    assert neutral is not None
    assert min(neutral, raw["p1_plus"]) <= final["final_p1_plus"] <= max(neutral, raw["p1_plus"])
    assert final["history_persistence_status"] == "DISABLED"


def test_final_probabilities_remain_coherent_and_ordered():
    records = pd.DataFrame(_graded_rows(120, 0.65, 0.70))
    final = calibration.build_final_intelligence(_raw_profile(), backtest_records=records, persist=False)
    assert 0.0 <= final["final_p3_plus"] <= final["final_p2_plus"] <= final["final_p1_plus"] <= 1.0
    assert final["final_p0"] == pytest.approx(1.0 - final["final_p1_plus"])
    assert final["final_p_exactly_1"] == pytest.approx(final["final_p1_plus"] - final["final_p2_plus"])
    assert final["final_fair_odds_1_plus"] is not None


def test_grade_is_capped_during_calibration_cold_start():
    # Even an otherwise A+ probability/confidence cannot publish above B+ before
    # the exact V2 raw model reaches the minimum empirical calibration sample.
    assert calibration.probability_grade(0.90, 95, "COLD_START") == "B+"
    assert calibration.probability_grade(0.90, 95, "WARMUP") == "A-"
    assert calibration.probability_grade(0.90, 95, "MATURE") == "A+"


def test_gated_step11_never_gets_a_manufactured_final_probability():
    final = calibration.build_final_intelligence(_raw_profile(probability_status="GATED", p1_plus=None), persist=False)
    assert final["final_status"] == "GATED"
    assert final["final_p1_plus"] is None
    assert final["final_fair_odds_1_plus"] is None


def test_calibration_module_has_no_new_network_client():
    source = inspect.getsource(calibration)
    assert "import requests" not in source
    assert "requests.get" not in source
    assert "statsapi.mlb.com" not in source
    assert "prediction_history" in source


def test_player_build_calls_certified_step11_then_finalizer():
    source = inspect.getsource(player._build_step12)
    assert "step11._build_step11" in source
    assert "calibration.build_final_intelligence" in source
    assert "step10._build_step10" not in source


def test_complete_panel_renders_steps_1_through_12_and_legacy_separately():
    source = inspect.getsource(player.render_player_layer)
    for marker in (
        "step1._render_step1",
        "step2._render_step2",
        "step3._render_step3",
        "step4._render_step4",
        "step5._render_step5",
        "step6._render_step6",
        "step7._render_step7",
        "step8._render_step8",
        "step9._render_step9",
        "step10._render_step10",
        "step11._build_step11",
        "_render_step11_profile",
        "_render_step12_profile",
    ):
        assert marker in source
    assert "with st.expander(V2_INTELLIGENCE_LABEL" in source
    assert "with st.expander(LEGACY_AUDIT_LABEL" in source
    assert "frozen_detail.render_player_layer" in source


def test_final_hub_uses_v2_player_but_keeps_daily_rankings_frozen():
    source = inspect.getsource(hub)
    assert "import mlb_matchup_player_v35 as player_layer" in source
    assert "import mlb_matchup_rankings_v21 as rankings" in source
    assert hub.FROZEN_V1_PRESENTATION == ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")
    assert "Daily Top 5 remains intentionally frozen" in source


def test_router_points_to_final_step12_hub():
    source = inspect.getsource(router)
    assert "from mlb_matchup_hub_v41 import" in source
