from devsystem.monster_speed_v3_step6_hot_cache_v1 import check_repository


def test_monster_speed_v3_step6_exact_lock_hot_cache_contract():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["root_locked_packages"] >= 40
    assert result["browser_locked_packages"] >= result["root_locked_packages"]
    assert result["active_browser_cache_owners"] == 5
    assert result["cache_identity"] == "OS + PYTHON + EXACT_LOCKS_ONLY"
    assert result["requirements_comments_invalidate_browser_cache"] is False
    assert result["deployment_markers_invalidate_browser_cache"] is False
    assert result["browser_cache_epoch_invalidate_browser_cache"] is False
    assert result["cache_miss_installs_exact_lock"] is True
    assert result["hot_cache_hit_required"] is True
    assert result["product_runtime_changed"] is False
