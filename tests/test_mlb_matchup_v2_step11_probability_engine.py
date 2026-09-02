from __future__ import annotations

from pathlib import Path

import pytest

import mlb_matchup_probability_v1 as engine
import mlb_matchup_player_v34 as player


ROOT = Path(__file__).resolve().parents[1]


def _profiles():
    foundation = {
        "player_id": 123,
        "player_name": "Test Hitter",
        "starter_id": 456,
        "valid_slot": True,
        "confirmed": True,
        "projected": False,
        "slot": 2,
    }
    hitter = {
        "hit_per_pa": 0.245,
        "xba": 0.280,
        "neutral_hit_skill": 0.275,
        "hitter_profile_score": 90,
    }
    starter = {
        "starter_strength_score": 50,
        "starter_strength_coverage": 1.0,
        "starter_profile_score": 90,
        "third_time_avg_delta": 0.0,
    }
    platoon = {
        "platoon_context_score": 50,
        "platoon_context_coverage": 1.0,
        "matchup_data_score": 90,
    }
    pitch = {
        "pitch_mix_score": 50,
        "pitch_mix_coverage": 1.0,
        "pitch_mix_data_score": 90,
    }
    batted = {
        "batted_ball_score": 50,
        "batted_ball_reliability": 1.0,
        "batted_ball_data_score": 90,
    }
    environment = {
        "environment_score": 50,
        "environment_coverage": 1.0,
        "environment_data_score": 90,
    }
    bullpen = {
        "bullpen_path_score": 50,
        "bullpen_quality_coverage": 1.0,
        "availability_index": 1.0,
        "bullpen_data_score": 90,
        "bullpen_inning_share": 0.40,
    }
    opportunity = {
        "ab_per_pa": 0.90,
        "expected_pa": 4.50,
        "nominal_starter_pa": 2.70,
        "nominal_bullpen_pa": 1.80,
        "opportunity_data_score": 90,
    }
    recent = {
        "recent_form_score": 50,
        "recent_form_coverage": 1.0,
        "stability_score": 80,
        "recent_data_score": 90,
    }
    return foundation, hitter, starter, platoon, pitch, batted, environment, bullpen, opportunity, recent


def test_step11_constants_and_role():
    assert engine.MONTE_CARLO_SIMS == 5_000_000
    assert engine.MONTE_CARLO_BATCH == 250_000
    assert engine.MONTE_CARLO_SEED == 110011
    assert player.PROBABILITY_IMPACT == "ACTIVE_RAW_V2"
    assert player.STEP11_ROLE == "RAW_HIT_PROBABILITY_ENGINE"


def test_base_hit_probability_anchors_on_hit_per_pa_and_expected_contact():
    _, hitter, _, _, _, _, _, _, opportunity, _ = _profiles()
    out = engine.base_hit_probability(hitter, opportunity)
    assert out["season_hit_per_pa"] == pytest.approx(0.245)
    assert out["xba_hit_per_pa"] == pytest.approx(0.252)
    assert out["base_hit_per_pa"] == pytest.approx(0.2471)


def test_tougher_starter_reduces_raw_starter_hit_probability():
    _, _, starter, platoon, pitch, batted, env, _, _, recent = _profiles()
    neutral = engine.starter_hit_probability(0.24, starter, platoon, pitch, batted, env, recent, 2.8)
    starter["starter_strength_score"] = 75
    tough = engine.starter_hit_probability(0.24, starter, platoon, pitch, batted, env, recent, 2.8)
    assert tough["probability"] < neutral["probability"]


def test_favorable_platoon_and_pitch_mix_raise_starter_probability():
    _, _, starter, platoon, pitch, batted, env, _, _, recent = _profiles()
    neutral = engine.starter_hit_probability(0.24, starter, platoon, pitch, batted, env, recent, 2.8)
    platoon["platoon_context_score"] = 70
    pitch["pitch_mix_score"] = 70
    favorable = engine.starter_hit_probability(0.24, starter, platoon, pitch, batted, env, recent, 2.8)
    assert favorable["probability"] > neutral["probability"]


def test_tougher_bullpen_reduces_bullpen_probability():
    _, _, _, _, _, batted, env, bullpen, _, recent = _profiles()
    neutral = engine.bullpen_hit_probability(0.24, bullpen, batted, env, recent)
    bullpen["bullpen_path_score"] = 75
    tough = engine.bullpen_hit_probability(0.24, bullpen, batted, env, recent)
    assert tough["probability"] < neutral["probability"]


def test_segment_exposure_preserves_expected_pa_and_step9_split():
    *_, bullpen, opportunity, _ = _profiles()
    exposure = engine.segment_exposure(opportunity, bullpen)
    assert exposure["status"] == "VERIFIED"
    assert exposure["starter_pa"] + exposure["bullpen_pa"] == pytest.approx(4.50)
    assert exposure["starter_pa"] == pytest.approx(2.70)
    assert exposure["bullpen_pa"] == pytest.approx(1.80)


def test_segment_exposure_fails_closed_when_split_unavailable():
    opportunity = {"expected_pa": 4.4}
    exposure = engine.segment_exposure(opportunity, {})
    assert exposure["status"] == "GATED"
    assert exposure["starter_pa"] is None
    assert exposure["bullpen_pa"] is None


def test_analytical_distribution_matches_four_equal_pas():
    out = engine.analytical_distribution(2.0, 2.0, 0.25, 0.25)
    assert sum(out["distribution"].values()) == pytest.approx(1.0)
    assert out["p0"] == pytest.approx(0.75**4)
    assert out["p1_plus"] == pytest.approx(1.0 - 0.75**4)
    assert out["expected_hits"] == pytest.approx(1.0)


def test_fractional_pa_is_preserved_without_rounding_away_opportunity():
    out = engine.analytical_distribution(2.5, 1.25, 0.20, 0.30)
    assert sum(out["distribution"].values()) == pytest.approx(1.0)
    assert out["expected_hits"] == pytest.approx(2.5 * 0.20 + 1.25 * 0.30)


def test_monte_carlo_zero_sigma_tracks_point_distribution():
    point = engine.analytical_distribution(2.0, 2.0, 0.22, 0.26)
    mc = engine.monte_carlo_distribution(
        2.0,
        2.0,
        0.22,
        0.26,
        0.0,
        0.0,
        simulations=200_000,
        seed=777,
        batch_size=50_000,
    )
    assert mc["p1_plus"] == pytest.approx(point["p1_plus"], abs=0.004)
    assert mc["expected_hits"] == pytest.approx(point["expected_hits"], abs=0.01)
    assert mc["simulations"] == 200_000
    assert mc["batches"] == 4
    assert mc["seed"] == 777


def test_probability_profile_outputs_raw_distribution_when_essential_inputs_exist():
    profiles = _profiles()
    out = engine.build_probability_profile(*profiles, simulations=80_000)
    assert out["probability_status"] in {"READY_RAW", "PROVISIONAL_RAW"}
    assert 0 < out["p0"] < 1
    assert 0 < out["p1_plus"] < 1
    assert 0 <= out["p2_plus"] <= out["p1_plus"]
    assert out["expected_hits"] > 0
    assert out["raw_fair_odds_1_plus"] is not None
    assert out["calibration_status"] == "DEFERRED_TO_STEP12"


def test_probability_profile_gates_missing_expected_pa():
    profiles = list(_profiles())
    profiles[8] = {"ab_per_pa": 0.90, "opportunity_data_score": 90}
    out = engine.build_probability_profile(*profiles, simulations=1_000)
    assert out["probability_status"] == "GATED"
    assert out["p1_plus"] is None
    assert out["probability_gates"]


def test_raw_fair_odds_are_mathematical_and_not_step12_calibration():
    assert engine.american_fair_odds(0.60) == -150
    assert engine.american_fair_odds(0.40) == 150
    source = (ROOT / "mlb_matchup_probability_v1.py").read_text()
    assert "DEFERRED_TO_STEP12" in source
    assert "def calibration" not in source.lower()
    assert "final_grade" not in source


def test_steps_1_through_11_accumulate_in_one_v2_panel_and_v1_stays_separate():
    source = (ROOT / "mlb_matchup_player_v34.py").read_text()
    for step in range(1, 11):
        assert f"step{step}._render_step{step}(games_df)" in source
    assert "_render_step11(games_df)" in source
    assert "with st.expander(V2_INTELLIGENCE_LABEL" in source
    assert "with st.expander(LEGACY_AUDIT_LABEL" in source
    assert "frozen_detail.render_player_layer" in source


def test_hub_and_router_point_to_step11_without_moving_rankings():
    hub = (ROOT / "mlb_matchup_hub_v40.py").read_text()
    router = (ROOT / "mlb_matchup_hub_v27.py").read_text()
    assert "import mlb_matchup_player_v34 as player_layer" in hub
    assert "import mlb_matchup_rankings_v21 as rankings" in hub
    assert 'FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")' in hub
    assert "from mlb_matchup_hub_v40 import" in router
