from copy import deepcopy
from pathlib import Path

import pytest

from sports_api.mlb_step7a_daily_game_picks_api_integration_v1 import (
    API_CONNECTED,
    DATA_TYPE,
    FALLBACK,
    evaluate_daily_game_picks_api_integration,
)


def live_state(**overrides):
    base = {
        "available": True,
        "data_type": "mlb_live_market_context_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "api_data_type": "mlb_live_odds_api_response_v1",
        "collected_at_utc": "2026-08-31T18:20:00+00:00",
        "match_method": "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "attached_count": 2,
        "contexts_by_game_id": {
            824314: {"official_game_id": 824314},
            824911: {"official_game_id": 824911},
        },
    }
    base.update(overrides)
    return base


def step6_state(**overrides):
    base = {
        "data_type": "mlb_step6g_controlled_graduation_v1",
        "graduated_production_active": True,
        "production_exposure_changed": False,
        "same_step5_10_cohort": True,
        "same_step5_9_gate": True,
        "exact_session_rollback": True,
        "global_kill_switch_available": True,
        "player_props_passthrough": True,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wnba_impact": False,
    }
    base.update(overrides)
    return base


def test_green_exact_id_states_activate_api_page_boundary():
    out = evaluate_daily_game_picks_api_integration(live_state(), step6_state())
    assert out["data_type"] == DATA_TYPE
    assert out["integration_status"] == API_CONNECTED
    assert out["api_integration_active"] is True
    assert out["attached_game_count"] == 2
    assert out["context_game_count"] == 2
    assert out["fallback_matching_used"] is False
    assert out["production_exposure_changed"] is False
    assert out["player_props_passthrough"] is True
    assert out["failures"] == []


@pytest.mark.parametrize(
    ("changes", "failure"),
    [
        ({"available": False}, "live_market_context_unavailable"),
        ({"data_type": "bad"}, "unexpected_live_market_context_data_type"),
        ({"api_data_type": "bad"}, "unexpected_api_data_type"),
        ({"source": "OtherBook"}, "unexpected_live_market_source"),
        ({"match_method": "team_name"}, "exact_official_game_id_join_not_proven"),
        ({"fallback_matching_used": True}, "fallback_or_fuzzy_matching_detected"),
        ({"contexts_by_game_id": None}, "contexts_by_game_id_missing"),
        ({"attached_count": 1}, "attached_count_context_count_mismatch"),
    ],
)
def test_live_market_contract_drift_falls_back(changes, failure):
    out = evaluate_daily_game_picks_api_integration(live_state(**changes), step6_state())
    assert out["integration_status"] == FALLBACK
    assert out["api_integration_active"] is False
    assert out["page_fallback_behavior_preserved"] is True
    assert failure in out["failures"]


@pytest.mark.parametrize(
    ("changes", "failure"),
    [
        ({"data_type": "bad"}, "step6g_presentation_state_unavailable"),
        ({"graduated_production_active": False}, "step6g_graduated_production_not_active"),
        ({"production_exposure_changed": True}, "step6g_exposure_change_detected"),
        ({"same_step5_10_cohort": False}, "step5_10_cohort_not_preserved"),
        ({"same_step5_9_gate": False}, "step5_9_gate_not_preserved"),
        ({"exact_session_rollback": False}, "exact_session_rollback_not_preserved"),
        ({"global_kill_switch_available": False}, "global_kill_switch_not_preserved"),
        ({"player_props_passthrough": False}, "player_prop_passthrough_not_preserved"),
        ({"model_math_impact": True}, "model_math_impact_drift"),
        ({"pick_strength_impact": True}, "pick_strength_impact_drift"),
        ({"ranking_math_impact": True}, "ranking_math_impact_drift"),
        ({"risk_logic_impact": True}, "risk_logic_impact_drift"),
        ({"wnba_impact": True}, "wnba_impact_drift"),
    ],
)
def test_step6_or_protected_drift_falls_back(changes, failure):
    out = evaluate_daily_game_picks_api_integration(live_state(), step6_state(**changes))
    assert out["integration_status"] == FALLBACK
    assert out["api_integration_active"] is False
    assert failure in out["failures"]


def test_empty_but_valid_live_slate_can_still_prove_api_transport():
    out = evaluate_daily_game_picks_api_integration(
        live_state(attached_count=0, contexts_by_game_id={}),
        step6_state(),
    )
    assert out["api_integration_active"] is True
    assert out["attached_game_count"] == 0


def test_missing_states_fail_open_to_frozen_step6_page():
    out = evaluate_daily_game_picks_api_integration(None, None)
    assert out["integration_status"] == FALLBACK
    assert out["page_fallback_behavior_preserved"] is True
    assert out["production_exposure_changed"] is False
    assert out["model_math_impact"] is False
    assert out["wnba_impact"] is False


def test_inputs_are_not_mutated():
    live = live_state()
    step6 = step6_state()
    before_live = deepcopy(live)
    before_step6 = deepcopy(step6)
    evaluate_daily_game_picks_api_integration(live, step6)
    assert live == before_live
    assert step6 == before_step6


def test_active_guard_routes_through_step7a_not_direct_step6g():
    text = Path("mlb_daily_game_picks_v217_guard.py").read_text()
    assert "install_step7a_daily_game_picks_api_integration" in text
    assert "install_step7a_daily_game_picks_api_integration(games_df)" in text
    assert "install_step6g_controlled_graduation_layer(games_df)" not in text


def test_step7a_presentation_is_additive_and_calls_frozen_step6g():
    text = Path("mlb_daily_game_picks_step7a_api_integration_v1.py").read_text()
    assert "step6g.install_step6g_controlled_graduation_layer(games_df)" in text
    assert "st.caption(" in text
    assert "st.error(" not in text
    assert "st.stop(" not in text
    assert "st.rerun(" not in text
