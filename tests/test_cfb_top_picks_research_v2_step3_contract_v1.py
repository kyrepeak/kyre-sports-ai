from devsystem.cfb_top_picks_research_v2_step3_history_v1 import check_repository


def test_step3_multisource_history_contract_is_frozen():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["independent_history_sources"] >= 2
    assert result["alias_resolution_required"] is True
    assert result["false_no_history_forbidden"] is True
    assert result["history_projection_weight"] == 0.0
    assert result["api2_protected"] is True
    assert result["steps1_2_protected"] is True
