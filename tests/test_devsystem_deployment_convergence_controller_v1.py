from __future__ import annotations

from copy import deepcopy

import pytest

from devsystem.deployment_convergence_controller_v1 import (
    FULL_REDEPLOY,
    REFRESH,
    VERIFY_RUNTIME,
    DeploymentConvergenceFailure,
    build_convergence_decision,
    contract_self_test,
    validate_convergence_decision,
)

EXPECTED = "a" * 40
STALE = "b" * 40


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["stale_gets_one_refresh"] is True
    assert result["stale_after_refresh_gets_one_redeploy"] is True
    assert result["stale_after_both_stops"] is True
    assert result["exact_sha_after_verify_never_redeploys"] is True


@pytest.mark.parametrize("phase", ["QUEUED", "BUILDING", "ACTIVATING"])
def test_in_flight_deployments_wait_for_event(phase):
    result = build_convergence_decision(expected_sha=EXPECTED, deploy_phase=phase)
    assert result["state"] == "DEPLOYMENT_IN_FLIGHT"
    assert result["next_legal_action"] == "WAIT_FOR_DEPLOYMENT_EVENT"
    assert result["deployment_mutation_requested"] is False


def test_live_stale_sha_has_bounded_refresh_then_redeploy():
    first = build_convergence_decision(
        expected_sha=EXPECTED,
        observed_sha=STALE,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
    )
    assert first["next_legal_action"] == REFRESH

    second = build_convergence_decision(
        expected_sha=EXPECTED,
        observed_sha=STALE,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
        consumed_actions=[REFRESH],
    )
    assert second["next_legal_action"] == FULL_REDEPLOY

    exhausted = build_convergence_decision(
        expected_sha=EXPECTED,
        observed_sha=STALE,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
        consumed_actions=[REFRESH, FULL_REDEPLOY],
    )
    assert exhausted["state"] == "DEPLOYMENT_RECOVERY_EXHAUSTED"
    assert exhausted["next_legal_action"] == "CLASSIFY_DEPLOYMENT_CONVERGENCE_FAILURE"
    assert exhausted["deployment_mutation_requested"] is False


def test_failed_deployment_gets_only_one_full_redeploy():
    first = build_convergence_decision(expected_sha=EXPECTED, deploy_phase="FAILED")
    assert first["next_legal_action"] == FULL_REDEPLOY

    exhausted = build_convergence_decision(
        expected_sha=EXPECTED,
        deploy_phase="FAILED",
        consumed_actions=[FULL_REDEPLOY],
    )
    assert exhausted["next_legal_action"] == "CLASSIFY_DEPLOYMENT_CONVERGENCE_FAILURE"


def test_exact_sha_runtime_failure_never_redeploys():
    first = build_convergence_decision(
        expected_sha=EXPECTED,
        observed_sha=EXPECTED,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=False,
        ui_ok=True,
    )
    assert first["next_legal_action"] == VERIFY_RUNTIME

    second = build_convergence_decision(
        expected_sha=EXPECTED,
        observed_sha=EXPECTED,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=False,
        ui_ok=True,
        consumed_actions=[VERIFY_RUNTIME],
    )
    assert second["state"] == "RUNTIME_OR_VERIFIER_FAILURE"
    assert second["next_legal_action"] == "CLASSIFY_RUNTIME_OR_VERIFIER_FAILURE"
    assert second["deployment_mutation_requested"] is False


def test_exact_sha_and_green_runtime_converges():
    result = build_convergence_decision(
        expected_sha=EXPECTED,
        observed_sha=EXPECTED,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
    )
    assert result["converged"] is True
    assert result["next_legal_action"] == "FREEZE_DEPLOYMENT_CONVERGENCE"


def test_live_without_identity_waits_instead_of_redeploying():
    result = build_convergence_decision(
        expected_sha=EXPECTED,
        deploy_phase="LIVE",
    )
    assert result["state"] == "DEPLOYMENT_IDENTITY_NOT_READY"
    assert result["next_legal_action"] == "WAIT_FOR_DEPLOYMENT_IDENTITY_EVENT"


def test_unknown_action_fails_closed():
    with pytest.raises(DeploymentConvergenceFailure):
        build_convergence_decision(
            expected_sha=EXPECTED,
            observed_sha=STALE,
            deploy_phase="LIVE",
            consumed_actions=["REDEPLOY_FOREVER"],
        )


def test_tamper_fails_closed():
    result = build_convergence_decision(
        expected_sha=EXPECTED,
        observed_sha=EXPECTED,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
    )
    tampered = deepcopy(result)
    tampered["next_legal_action"] = FULL_REDEPLOY
    with pytest.raises(DeploymentConvergenceFailure):
        validate_convergence_decision(tampered)


def test_controller_never_grants_product_patch_or_mutation_authority():
    result = build_convergence_decision(
        expected_sha=EXPECTED,
        observed_sha=STALE,
        deploy_phase="LIVE",
        health_ok=True,
        readiness_ok=True,
        ui_ok=True,
    )
    assert result["product_patch_allowed"] is False
    assert result["protections"]["step_2a_required_for_external_action"] is True
    assert result["protections"]["scope_lease_required_for_external_action"] is True
    assert result["protections"]["mutation_authority_granted"] is False
    assert result["protections"]["auto_mutate"] is False
