from __future__ import annotations

from devsystem import production_contract_v1 as contract


def _service(branch: str = contract.RENDER_RELEASE_BRANCH) -> dict:
    return {
        "name": contract.SERVICE_NAME,
        "id": contract.SERVICE_ID,
        "repo": contract.REPOSITORY,
        "branch": branch,
        "autoDeploy": contract.EXPECTED_AUTO_DEPLOY,
        "suspended": "not_suspended",
        "serviceDetails": {
            "healthCheckPath": contract.EXPECTED_HEALTH_PATH,
            "url": contract.PUBLIC_URL,
        },
    }


def test_render_hosting_config_can_be_green_independent_of_code_parity():
    result = contract.evaluate_render_service(_service())
    assert result["status"] == "GREEN"
    assert result["violations"] == []
    assert result["expected"]["branch"] == contract.RENDER_RELEASE_BRANCH


def test_render_hosting_config_fails_closed_on_branch_drift():
    result = contract.evaluate_render_service(_service(branch="wrong-branch"))
    assert result["status"] == "RED"
    assert "release_branch_config_mismatch" in result["violations"]


def test_release_parity_green_only_when_release_and_main_are_identical():
    green = contract.evaluate_release_parity(
        {"status": "identical", "ahead_by": 0, "behind_by": 0}
    )
    assert green["status"] == "GREEN"
    assert green["parity"] is True

    red = contract.evaluate_release_parity(
        {"status": "diverged", "ahead_by": 1199, "behind_by": 63}
    )
    assert red["status"] == "RED"
    assert red["main_only_commits"] == 1199
    assert red["release_only_commits"] == 63
    assert "release_missing_main_commits:1199" in red["violations"]
    assert "release_has_unmerged_commits:63" in red["violations"]
