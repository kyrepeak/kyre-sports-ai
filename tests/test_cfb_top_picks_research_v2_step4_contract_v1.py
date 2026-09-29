from devsystem.cfb_top_picks_research_v2_step4_offense_v1 import check_repository


def test_step4_offense_contract_is_green():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["core_metrics_per_team"] == 5
    assert result["supporting_metrics_per_team"] == 4
    assert result["field_level_provenance"] is True
    assert result["multi_source"] is True
    assert result["projection_weight"] == 0.0
    assert result["api2_protected"] is True
