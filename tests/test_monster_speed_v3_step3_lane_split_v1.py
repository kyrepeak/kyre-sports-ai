from devsystem.monster_speed_v3_step3_lane_split_v1 import check_repository

def test_monster_speed_v3_step3_lane_split():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["pr_mode"] == "FAST"
    assert result["merged_main_mode"] == "FULL"
    assert result["routine_pr_browser_qa"] is False
    assert result["high_risk_model_pr_full_sport_proof"] is True
    assert result["full_merge_required_on_main"] is True
