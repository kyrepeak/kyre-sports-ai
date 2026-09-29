from devsystem.monster_speed_v3_step1_quarantine_v1 import check_repository


def test_monster_speed_v3_step1_app_fanout_quarantine():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["checked"] == 51
    assert result["quarantined_workflows"] == 51
    assert result["baseline_runs"] == 56
    assert result["unrelated_app_runs_removed"] == 51
    assert result["expected_max_runs_from_same_app_only_shape"] == 5
