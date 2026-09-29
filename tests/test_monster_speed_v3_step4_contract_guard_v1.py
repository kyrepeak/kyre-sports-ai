from devsystem.monster_speed_v3_step4_contract_guard_v1 import check_repository

def test_monster_speed_v3_step4_contract_guard():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["blocking_truth"] == "USER_VISIBLE_BEHAVIOR"
    assert result["telemetry_default"] == "NON_BLOCKING"
    assert result["responsive_widths"] == [390, 768, 1440]
    assert result["stable_selectors_required"] is True
    assert result["preserved_markets_required"] is True
    assert result["zero_horizontal_overflow_required"] is True
    assert result["product_runtime_changed"] is False
