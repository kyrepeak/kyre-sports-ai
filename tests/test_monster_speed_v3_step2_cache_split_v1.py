from devsystem.monster_speed_v3_step2_cache_split_v1 import check_repository

def test_monster_speed_v3_step2_cache_split():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["root_dependencies"] == 8
    assert result["active_workflows"] == 3
    assert result["comment_only_redeploy_invalidates_cache"] is False
    assert result["dependency_change_invalidates_cache"] is True
