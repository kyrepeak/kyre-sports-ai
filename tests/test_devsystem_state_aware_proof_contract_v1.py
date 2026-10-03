import pytest

from devsystem.state_aware_proof_contract_v1 import (
    StateAwareProofFailure,
    evaluate_state,
    self_test,
)


def test_self_test_green_and_read_only():
    result = self_test()
    assert result["status"] == "GREEN"
    assert result["ready_contract_green"] is True
    assert result["wait_is_valid_nonfailure_state"] is True
    assert result["transient_noise_ignored"] is True
    assert result["reconciliation_requires_state_progress"] is True
    assert result["terminal_failure_is_valid_but_not_green"] is True
    assert result["blocked_state_denies_mutation"] is True
    assert result["invalid_wait_fails_closed"] is True
    assert result["blind_polling_allowed"] is False
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False


def test_ready_requires_only_stable_terminal_evidence():
    result = evaluate_state(
        "READY",
        {
            "source_contract_green": True,
            "focused_proof_green": True,
            "devsystem_final_gate_green": True,
            "terminal_receipt_green": True,
            "frozen_registry_aligned": True,
            "observed_at": "noise",
            "temporary_selector_present": False,
        },
    )
    assert result["status"] == "GREEN"
    assert result["green_eligible"] is True
    assert "observed_at" in result["ignored_transient_keys"]
    assert "temporary_selector_present" in result["ignored_transient_keys"]


def test_wait_is_valid_even_when_temporary_runtime_condition_is_not_ready():
    result = evaluate_state(
        "WAIT",
        {
            "wait_decision": "WAIT",
            "wait_state_token": "WAIT-DEPLOYMENT-1",
            "resume_trigger": "deployment_identity_changed",
            "event_driven_resume": True,
            "public_runtime_ready": False,
            "deployment_sha_match": False,
        },
    )
    assert result["valid_state"] is True
    assert result["green_eligible"] is False
    assert result["rerun_allowed"] is False


def test_transient_observations_do_not_change_wait_contract_identity():
    base = {
        "wait_decision": "WAIT",
        "wait_state_token": "WAIT-STABLE-TOKEN",
        "resume_trigger": "deployment_identity_changed",
        "event_driven_resume": True,
    }
    first = evaluate_state("WAIT", {**base, "poll_count": 1, "observed_at": "a"})
    second = evaluate_state(
        "WAIT",
        {**base, "poll_count": 999, "observed_at": "b", "temporary_http_status": 503},
    )
    assert first["contract_fingerprint"] == second["contract_fingerprint"]


def test_wait_without_resume_identity_fails_closed():
    result = evaluate_state(
        "WAIT",
        {
            "wait_decision": "WAIT",
            "wait_state_token": "",
            "resume_trigger": "",
            "event_driven_resume": False,
        },
    )
    assert result["status"] == "BLOCKED"
    assert result["valid_state"] is False
    assert "WAIT_STATE_TOKEN_MISSING" in result["reasons"]


def test_reconciliation_requires_authority_and_state_hash_progress():
    good = evaluate_state(
        "RECONCILING",
        {
            "reconciliation_decision": "AUTO_RECONCILIATION_PLANNED",
            "apply_allowed": True,
            "previous_state_hash": "a" * 64,
            "next_state_hash": "b" * 64,
            "retry_after_state_change_only": True,
        },
    )
    bad = evaluate_state(
        "RECONCILING",
        {
            "reconciliation_decision": "AUTO_RECONCILIATION_PLANNED",
            "apply_allowed": True,
            "previous_state_hash": "a" * 64,
            "next_state_hash": "a" * 64,
            "retry_after_state_change_only": True,
        },
    )
    assert good["valid_state"] is True
    assert good["rerun_allowed"] is True
    assert bad["valid_state"] is False
    assert "REGISTRY_STATE_HASH_DID_NOT_ADVANCE" in bad["reasons"]


def test_terminal_failure_is_valid_state_but_never_green_eligible():
    result = evaluate_state(
        "FAILED",
        {
            "terminal_failure": True,
            "failure_domain": "PROOF_VERIFIER",
            "root_cause_fingerprint": "ROOT-XYZ",
            "next_legal_action": "PATCH_ONE_VERIFIER_ROOT",
        },
    )
    assert result["valid_state"] is True
    assert result["green_eligible"] is False
    assert result["mutation_authority_granted"] is False


def test_blocked_state_requires_mutation_denied():
    result = evaluate_state(
        "BLOCKED",
        {
            "blocker": "LEASE_CONFLICT",
            "next_legal_action": "WAIT_FOR_LEASE_RELEASE",
            "mutation_allowed": True,
        },
    )
    assert result["valid_state"] is False
    assert "BLOCKED_STATE_MUST_DENY_MUTATION" in result["reasons"]


def test_unknown_state_fails_closed():
    with pytest.raises(StateAwareProofFailure, match="unsupported state"):
        evaluate_state("MAYBE", {})
