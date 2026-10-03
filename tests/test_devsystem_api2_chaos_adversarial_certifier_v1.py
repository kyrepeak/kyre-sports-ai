from copy import deepcopy

import pytest

from devsystem.api2_chaos_adversarial_certifier_v1 import (
    Api2ChaosCertificationFailure,
    run_certification,
    self_test,
    validate_certificate,
)


def test_step6_self_test_green_and_read_only():
    result = self_test()
    assert result["status"] == "GREEN"
    assert result["base_chaos_scenarios"] == 11
    assert result["api2_integration_scenarios"] == 5
    assert result["combined_scenarios"] == 16
    assert result["all_scenarios_pass"] is True
    assert result["slow_live_wait_protected"] is True
    assert result["transient_noise_idempotent"] is True
    assert result["frozen_edit_blocks_mutation"] is True
    assert result["deployment_drift_nonproduct_owned"] is True
    assert result["one_retry_after_registry_progress"] is True
    assert result["tamper_evident_certificate"] is True
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["product_runtime_mutation"] is False
    assert result["mutation_authority_granted"] is False
    assert result["blind_retry_allowed"] is False


def test_full_certificate_has_exact_scenario_counts():
    cert = run_certification()
    assert cert["monster_scenario_count"] == 11
    assert cert["api2_integration_scenario_count"] == 5
    assert cert["combined_scenario_count"] == 16
    assert cert["all_scenarios_pass"] is True
    assert all(
        scenario["passed"] is True
        for scenario in cert["api2_integration_scenarios"].values()
    )


def test_tampered_certificate_fails_closed():
    cert = run_certification()
    tampered = deepcopy(cert)
    tampered["api2_integration_scenarios"]["frozen_edit_blocks_mutation"]["passed"] = False
    with pytest.raises(Api2ChaosCertificationFailure, match="digest mismatch"):
        validate_certificate(tampered)


def test_duplicate_merge_and_detached_resume_remain_protected():
    cert = run_certification()
    safety = cert["safety"]
    assert safety["duplicate_merge_blocked"] is True
    assert safety["detached_resume_no_duplicate"] is True
    assert safety["slow_live_run_protected"] is True
    assert safety["step_2a_preserved"] is True
