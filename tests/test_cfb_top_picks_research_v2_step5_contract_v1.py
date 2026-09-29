from devsystem.cfb_top_picks_research_v2_step5_defense_pace_v1 import check_repository


def test_step5_defense_pace_contract_is_green():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["core_metrics_per_team"] == 4
    assert result["supporting_metrics_per_team"] == 6
    assert result["field_level_provenance"] is True
    assert result["multi_source"] is True
    assert result["projection_weight"] == 0.0
    assert result["api2_protected"] is True
    assert result["steps1_4_protected"] is True
