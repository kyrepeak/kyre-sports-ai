from __future__ import annotations

from devsystem import cfb_top_picks_repair_step5_final_closeout_v1 as cert


def test_step5_final_closeout_is_proof_only_and_keeps_api2_separate():
    assert cert.MISSION_STEP == "5/5"
    assert cert.API2_USED is False
    assert cert.MAY_MODIFY_PAGE is False
    assert cert.MAY_MODIFY_ROUTER is False
    assert cert.MAY_MODIFY_MODEL is False
    assert cert.MAY_MODIFY_PROJECTION is False
    assert cert.MAY_MODIFY_PROBABILITY is False
    assert cert.MAY_MODIFY_RANKING is False
    assert cert.MAY_MODIFY_SELECTION is False
    assert cert.MAY_MODIFY_SPORTSBOOK is False


def test_step5_final_closeout_requires_all_repaired_surfaces_and_responsive_proof():
    assert cert.REQUIRED_REPAIR_STEPS == (
        "MATCHUP_HISTORY_ROUTER",
        "DEFENSE_PACE_COMPLETENESS",
        "MARKET_AWARE_FOOTBALL_REASONING",
        "DETAIL_INTEGRITY",
    )
    assert cert.REQUIRED_VIEWPORTS == ((390, 844), (768, 1024), (1440, 1000))
    assert cert.REQUIRED_DETAIL_SECTIONS == (
        "Why This Pick",
        "Actual Matchup History",
        "Benefits",
        "Market-Aware Football Reasoning",
    )


def test_step5_repository_contract_is_current_v9_v5_and_fail_closed():
    result = cert.verify_repository_contract()
    assert result["status"] == "GREEN"
    assert result["current_v9_page"] is True
    assert result["current_v5_detail_builder"] is True
    assert result["step1_contract"] is True
    assert result["step2_contract"] is True
    assert result["step3_contract"] is True
    assert result["step4_contract"] is True
    assert result["legacy_step5_visual_contract"] is True
    assert result["public_host"] == "https://pickvault.streamlit.app"


def test_step5_live_payload_requires_step3_and_step4_green():
    payload = cert._finalize_live_payload(
        {"status": "GREEN", "ranked_picks_certified": 10, "all_reasoning_usable": True},
        {"status": "GREEN", "ranked_picks_certified": 10, "selected_matchup_detail_contract": True},
    )
    assert payload["status"] == "GREEN"
    assert payload["ranked_picks_certified"] == 10
    assert payload["step3_market_reasoning_green"] is True
    assert payload["step4_detail_integrity_green"] is True
    assert payload["projection_changed"] is False
    assert payload["probability_changed"] is False
    assert payload["ranking_changed"] is False
    assert payload["selection_changed"] is False


def test_step5_live_payload_fails_closed_if_prior_cert_is_not_green():
    try:
        cert._finalize_live_payload(
            {"status": "RED", "ranked_picks_certified": 10, "all_reasoning_usable": True},
            {"status": "GREEN", "ranked_picks_certified": 10, "selected_matchup_detail_contract": True},
        )
    except AssertionError as exc:
        assert "STEP5_STEP3_NOT_GREEN" in str(exc)
    else:
        raise AssertionError("Step 5 accepted a non-green Step 3 proof")
