from devsystem.monster_speed_v3_step3_lane_split_v1 import check_repository


def test_monster_speed_v3_step3_lane_split():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["pr_mode"] == "TARGETED_REQUIRED"
    assert result["merged_main_mode"] == "FULL"
    assert result["relevant_pr_browser_qa"] is True
    assert result["relevant_pr_sport_proof"] is True
    assert result["optional_pr_lanes_skippable"] is True
    assert result["required_pr_lanes_must_succeed"] is True
    assert result["full_merge_required_on_main"] is True
