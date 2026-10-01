from __future__ import annotations

from copy import deepcopy

import pytest

from devsystem.content_addressed_proof_reuse_v1 import (
    ProofReuseFailure,
    build_receipt,
    contract_self_test,
    evaluate_reuse,
    from_frozen_checkpoint,
)

A = "a" * 40
B = "b" * 40
C = "c" * 40
DIGEST = "sha256:" + "d" * 64
ARTIFACTS = {"feature.py": A, "tests/test_feature.py": B}
DEPENDENCIES = {"shared/contract.py": C}


def _receipt(**overrides):
    args = {
        "checkpoint_id": "STEP",
        "source_main_sha": A,
        "proof_run_id": 123,
        "terminal_receipt_digest": DIGEST,
        "proof_policy_version": "policy-v1",
        "proof_scope": ["STATIC_CONTRACT", "FOCUSED_TEST"],
        "artifacts": ARTIFACTS,
        "dependencies": DEPENDENCIES,
    }
    args.update(overrides)
    return build_receipt(**args)


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["identical_content_reuses_after_unrelated_head_move"] is True
    assert result["step_2a_still_required_for_mutation"] is True


def test_exact_content_can_reuse_after_unrelated_main_movement():
    result = evaluate_reuse(
        _receipt(),
        observed_artifacts=ARTIFACTS,
        observed_dependencies=DEPENDENCIES,
        required_scope=["STATIC_CONTRACT"],
        proof_policy_version="policy-v1",
        current_head_sha=B,
    )
    assert result["decision"] == "REUSE_APPROVED"
    assert result["reusable"] is True
    assert result["head_moved"] is True


@pytest.mark.parametrize(
    ("observed_artifacts", "observed_dependencies", "policy", "scope", "reason"),
    [
        ({**ARTIFACTS, "feature.py": C}, DEPENDENCIES, "policy-v1", ["STATIC_CONTRACT"], "ARTIFACT_BLOB_DRIFT"),
        (ARTIFACTS, {"shared/contract.py": A}, "policy-v1", ["STATIC_CONTRACT"], "DEPENDENCY_BLOB_DRIFT"),
        (ARTIFACTS, DEPENDENCIES, "policy-v2", ["STATIC_CONTRACT"], "PROOF_POLICY_DRIFT"),
        (ARTIFACTS, DEPENDENCIES, "policy-v1", ["PRODUCTION_CERTIFICATION"], "PROOF_SCOPE_INSUFFICIENT"),
    ],
)
def test_any_relevant_drift_requires_new_proof(observed_artifacts, observed_dependencies, policy, scope, reason):
    result = evaluate_reuse(
        _receipt(),
        observed_artifacts=observed_artifacts,
        observed_dependencies=observed_dependencies,
        required_scope=scope,
        proof_policy_version=policy,
        current_head_sha=B,
    )
    assert result["decision"] == "NEW_PROOF_REQUIRED"
    assert reason in result["reasons"]


def test_production_state_proof_is_never_content_reused():
    receipt = _receipt(proof_kind="PRODUCTION_STATE", proof_scope=["PRODUCTION_CERTIFICATION"])
    result = evaluate_reuse(
        receipt,
        observed_artifacts=ARTIFACTS,
        observed_dependencies=DEPENDENCIES,
        required_scope=["PRODUCTION_CERTIFICATION"],
        proof_policy_version="policy-v1",
        current_head_sha=B,
    )
    assert result["reusable"] is False
    assert "PROOF_KIND_NOT_CONTENT_REUSABLE" in result["reasons"]


def test_tampered_receipt_fails_closed():
    receipt = deepcopy(_receipt())
    receipt["artifacts"]["feature.py"] = C
    result = evaluate_reuse(
        receipt,
        observed_artifacts=ARTIFACTS,
        observed_dependencies=DEPENDENCIES,
        required_scope=["STATIC_CONTRACT"],
        proof_policy_version="policy-v1",
        current_head_sha=B,
    )
    assert result["decision"] == "NEW_PROOF_REQUIRED"
    assert result["reasons"] == ["INVALID_OR_TAMPERED_RECEIPT"]


def test_frozen_checkpoint_must_have_terminal_proof():
    with pytest.raises(ProofReuseFailure):
        from_frozen_checkpoint(
            {
                "status": "FROZEN",
                "checkpoint_id": "OLD_STEP",
                "source_main_sha": A,
                "artifacts": ARTIFACTS,
            },
            proof_policy_version="policy-v1",
            proof_scope=["STATIC_CONTRACT"],
            dependencies=DEPENDENCIES,
        )


def test_frozen_checkpoint_with_terminal_receipt_can_seed_reuse():
    receipt = from_frozen_checkpoint(
        {
            "status": "FROZEN",
            "checkpoint_id": "FROZEN_STEP",
            "source_main_sha": A,
            "proven_merge_sha": A,
            "proof_run_id": 999,
            "terminal_receipt_digest": DIGEST,
            "artifacts": ARTIFACTS,
        },
        proof_policy_version="policy-v1",
        proof_scope=["STATIC_CONTRACT"],
        dependencies=DEPENDENCIES,
    )
    assert receipt["checkpoint_id"] == "FROZEN_STEP"
    assert receipt["proof_run_id"] == 999
