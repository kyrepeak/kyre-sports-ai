from __future__ import annotations

from copy import deepcopy

from devsystem import monster_cfb_game_total_integration_final_closeout_step4_v1 as cert


def test_step4_closeout_is_proof_only_and_keeps_parallel_state_separate():
    assert cert.MISSION_STEP == "4/4"
    assert cert.WORKSTREAM == "monster-cfb-game-total-integration-repair-v1"
    assert cert.API2_USED is False
    assert cert.MAY_MODIFY_PAGE is False
    assert cert.MAY_MODIFY_ROUTER is False
    assert cert.MAY_MODIFY_MODEL is False
    assert cert.MAY_MODIFY_PROJECTION is False
    assert cert.MAY_MODIFY_PROBABILITY is False
    assert cert.MAY_MODIFY_PROVIDER is False
    assert cert.MAY_MODIFY_PAGE2 is False
    assert cert.MAY_MODIFY_OTHER_SPORTS is False
    assert cert.NETWORK_CALLS is False
    assert cert.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_step4_closeout_requires_exact_steps_1_3_contract_identities():
    assert cert.PRIOR_STEPS["step1"]["step"] == "1/4"
    assert cert.PRIOR_STEPS["step2"]["step"] == "2/4"
    assert cert.PRIOR_STEPS["step3"]["step"] == "3/4"
    assert cert.PRIOR_STEPS["step1"]["freeze_token"] == (
        "MONSTER_CFB_GAME_TOTAL_SHELL_INTEGRATION_STEP1_V1_FROZEN"
    )
    assert cert.PRIOR_STEPS["step2"]["freeze_token"] == (
        "MONSTER_CFB_GAME_TOTAL_RUNTIMEERROR_STEP2_V1_FROZEN"
    )
    assert cert.PRIOR_STEPS["step3"]["freeze_token"] == (
        "MONSTER_CFB_GAME_TOTAL_NATIVE_REGRESSION_STEP3_V1_FROZEN"
    )


def test_step4_repository_contract_composes_the_entire_repair_mission():
    result = cert.verify_repository_contract()
    assert result["status"] == "GREEN"
    assert result["step1_contract"] is True
    assert result["step2_contract"] is True
    assert result["step3_contract"] is True
    assert result["shared_cfb_shell_preserved"] is True
    assert result["cfb_market_set"] == (
        "Moneyline",
        "Over/Under",
        "Game Total",
        "Top Picks",
    )
    assert result["page1_owner"] == "cfb_game_total_clean_page_v43"
    assert result["runtime_repair"] == "cfb_game_total_clean_page_v44"
    assert result["stale_date_runtimeerror_repair_preserved"] is True
    assert result["page2_owner"] == "cfb_game_total_page2_step8_final_runtime_v1"
    assert result["temporary_seams_restore"] is True
    assert result["product_runtime_mutation"] is False
    assert result["model_projection_probability_mutation"] is False
    assert result["provider_mutation"] is False
    assert result["page2_mutation"] is False
    assert result["other_sports_mutation"] is False
    assert result["network_calls_added"] == 0
    assert result["sportsbook_projection_influence"] == 0.0
    assert result["api2_used"] is False


def test_step4_final_closeout_latches_only_a_green_composed_contract():
    result = cert.finalize_closeout(cert.verify_repository_contract())
    assert result["status"] == "GREEN"
    assert result["decision"] == "MONSTER_CFB_GAME_TOTAL_INTEGRATION_REPAIR_MISSION_GREEN"
    assert result["steps_1_3_composed"] is True
    assert result["product_runtime_mutation"] is False
    assert result["api2_used"] is False


def test_step4_final_closeout_fails_closed_on_prior_step_drift():
    payload = deepcopy(cert.verify_repository_contract())
    payload["step2_contract"] = False
    try:
        cert.finalize_closeout(payload)
    except AssertionError as exc:
        assert "STEP4_REQUIRED_CONTRACT_RED:step2_contract" in str(exc)
    else:
        raise AssertionError("Step 4 accepted a red Step 2 contract")


def test_step4_final_closeout_fails_closed_on_protected_scope_mutation():
    payload = deepcopy(cert.verify_repository_contract())
    payload["provider_mutation"] = True
    try:
        cert.finalize_closeout(payload)
    except AssertionError as exc:
        assert "STEP4_PROTECTED_SCOPE_MUTATED:provider_mutation" in str(exc)
    else:
        raise AssertionError("Step 4 accepted a protected-scope mutation")
