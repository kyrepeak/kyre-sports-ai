from __future__ import annotations

from copy import deepcopy

import pytest

A = "a" * 40
B = "b" * 40
C = "c" * 40
ARTIFACTS = {
    "runless_proof_plane/executor.py": "1" * 40,
    "tests/test_feature.py": "2" * 40,
}
DEPENDENCIES = {
    "runless_proof_plane/prove.py": "3" * 40,
    "devsystem/runless_proof_plan_v1.py": "4" * 40,
}
POLICY = {
    "task_id": "example-task",
    "workstream": "example-workstream",
    "commands": [["python", "-m", "pytest", "-q", "tests/test_feature.py"]],
    "probes": [],
    "timeout_seconds": 900,
    "live_ttl_seconds": 900,
    "freeze_token": "EXAMPLE_FROZEN",
}


def _subject():
    try:
        from runless_proof_plane.postmerge_reuse import evaluate_postmerge_reuse
    except ModuleNotFoundError:
        pytest.fail("post-merge proof reuse implementation is missing")
    return evaluate_postmerge_reuse


def _receipt(**overrides):
    receipt = {
        "proof_id": "example-task-aaaaaaaaaaaaaaaa-0123456789abcdef",
        "task_id": "example-task",
        "workstream": "example-workstream",
        "candidate_sha": A,
        "digest": "d" * 64,
        "failure_class": "NONE",
        "proof_fingerprint": "f" * 64,
        "artifact_map": ARTIFACTS,
        "dependency_map": DEPENDENCIES,
    }
    receipt.update(overrides)
    return receipt


def _evaluate(**overrides):
    kwargs = {
        "premerge_receipt": _receipt(),
        "merged_main_sha": B,
        "merged_artifacts": ARTIFACTS,
        "merged_dependencies": DEPENDENCIES,
        "candidate_policy": POLICY,
        "merged_policy": POLICY,
        "candidate_is_ancestor": True,
        "proof_run_id": 321,
    }
    kwargs.update(overrides)
    return _subject()(**kwargs)


def test_identical_static_content_reuses_premerge_terminal_proof_after_merge():
    result = _evaluate()
    assert result["decision"] == "REUSE_APPROVED"
    assert result["reusable"] is True
    assert result["head_moved"] is True
    assert result["static_evidence_reexecuted"] is False
    assert result["github_actions_enabled"] is False
    assert result["next_legal_action"] == "PUBLISH_REUSED_GATE"
    assert result["source_candidate_sha"] == A
    assert result["merged_main_sha"] == B


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"merged_artifacts": {**ARTIFACTS, "runless_proof_plane/executor.py": C}}, "ARTIFACT_BLOB_DRIFT"),
        ({"merged_dependencies": {**DEPENDENCIES, "runless_proof_plane/prove.py": C}}, "DEPENDENCY_BLOB_DRIFT"),
        ({"merged_policy": {**POLICY, "timeout_seconds": 901}}, "PROOF_POLICY_DRIFT"),
        ({"merged_policy": {**POLICY, "probes": [{"name": "live"}]}}, "DYNAMIC_PROOF_NOT_REUSABLE"),
        ({"candidate_is_ancestor": False}, "CANDIDATE_NOT_ANCESTOR"),
        ({"premerge_receipt": _receipt(failure_class="STATIC_TEST_FAILURE")}, "TERMINAL_PROOF_NOT_SUCCESS"),
    ],
)
def test_any_relevant_drift_fails_closed_to_new_proof(overrides, reason):
    result = _evaluate(**overrides)
    assert result["decision"] == "NEW_PROOF_REQUIRED"
    assert result["reusable"] is False
    assert reason in result["reasons"]
    assert result["next_legal_action"] == "RUN_NEW_PROOF"
    assert result["static_evidence_reexecuted"] is False


def test_tampered_premerge_digest_fails_closed():
    receipt = deepcopy(_receipt())
    receipt["digest"] = "not-a-digest"
    result = _evaluate(premerge_receipt=receipt)
    assert result["decision"] == "NEW_PROOF_REQUIRED"
    assert result["reusable"] is False
    assert "INVALID_PREMERGE_RECEIPT" in result["reasons"]


def test_same_head_is_not_a_postmerge_reuse_case():
    result = _evaluate(merged_main_sha=A)
    assert result["decision"] == "NEW_PROOF_REQUIRED"
    assert "HEAD_DID_NOT_MOVE" in result["reasons"]
