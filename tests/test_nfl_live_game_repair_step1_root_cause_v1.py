from __future__ import annotations

from devsystem import nfl_live_game_repair_step1_root_cause_v1 as cert


def test_step1_is_diagnostic_only_and_keeps_product_frozen():
    assert cert.MISSION_STEP == "1/5"
    assert cert.MAY_MODIFY_PRODUCT_RUNTIME is False
    assert cert.MAY_MODIFY_PROJECTION is False
    assert cert.MAY_MODIFY_PROBABILITY is False
    assert cert.MAY_MODIFY_RANKING is False
    assert cert.MAY_MODIFY_SPORTSBOOK is False
    assert cert.API2_USED is False


def test_step1_proves_current_router_owners_and_shared_gate():
    result = cert.verify_repository_root_cause()
    assert result["status"] == "GREEN"
    assert result["rushing_owner"] == "nfl_rushing_yards_hub_v16"
    assert result["receiving_owner"] == "nfl_receiving_yards_hub_v17"
    assert result["shared_gate"] == "nfl_prop_app_eligibility_v1.py"
    assert result["both_pages_call_shared_guard"] is True


def test_step1_proves_kickoff_itself_closes_identity_contract():
    result = cert.verify_repository_root_cause()
    assert result["live_state_forced_closed"] is True
    assert result["guard_accepts_only_pregame_identity_states"] is True
    assert result["live_game_context_blocked_by_shared_gate"] is True
    assert result["root_cause_class"] == "PREGAME_ONLY_APP_IDENTITY_GATE"


def test_step1_separates_old_pregame_pr_from_new_live_game_mission():
    result = cert.verify_repository_root_cause()
    assert result["old_pregame_fix_not_authoritative"] is True
    assert result["next_patch_owner"] == "nfl_prop_app_eligibility_v1.py"
    assert result["page_specific_patch_required"] is False
