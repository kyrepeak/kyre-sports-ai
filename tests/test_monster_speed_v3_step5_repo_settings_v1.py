from __future__ import annotations

import pytest

from devsystem.monster_speed_v3_step5_repo_settings_v1 import (
    Step5SettingsFailure,
    validate_local_safety_contract,
    validate_repository_settings,
)


def _payload(**overrides):
    payload = {
        "full_name": "kyrepeak/kyre-sports-ai",
        "default_branch": "main",
        "allow_auto_merge": True,
        "allow_update_branch": True,
        "allow_squash_merge": True,
        "allow_merge_commit": True,
        "allow_rebase_merge": True,
    }
    payload.update(overrides)
    return payload


def test_step5_accepts_required_repo_settings():
    result = validate_repository_settings(_payload())
    assert result["status"] == "GREEN"
    assert result["allow_auto_merge"] is True
    assert result["allow_update_branch"] is True


@pytest.mark.parametrize(
    "mutation,token",
    [
        ({"allow_auto_merge": False}, "allow_auto_merge"),
        ({"allow_update_branch": False}, "allow_update_branch"),
        ({"default_branch": "develop"}, "default_branch"),
    ],
)
def test_step5_fails_closed_on_repo_setting_regression(mutation, token):
    with pytest.raises(Step5SettingsFailure, match=token):
        validate_repository_settings(_payload(**mutation))


def test_step5_preserves_existing_devsystem_gate_contract():
    result = validate_local_safety_contract()
    assert result["status"] == "GREEN"
    assert result["devsystem_final_gate_preserved"] is True
    assert result["fast_pr_gate_preserved"] is True
    assert result["full_merge_gate_preserved"] is True
    assert result["branch_protection_mutated"] is False
    assert result["product_runtime_changed"] is False
