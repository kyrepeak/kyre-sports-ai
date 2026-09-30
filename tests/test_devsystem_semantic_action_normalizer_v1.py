from __future__ import annotations

from copy import deepcopy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.semantic_action_normalizer_v1 import (
    SemanticActionNormalizerFailure,
    canonicalize_action,
    contract_self_test,
    normalize_action_type,
    normalize_target,
    semantic_fingerprint,
    validate_normalization_proof,
)


def test_pr_target_aliases_collapse_to_one_identity():
    repo = "KyrePeak/Kyre-Sports-AI"
    variants = [
        "PR #1222",
        "pr/1222",
        "github:pr/1222",
        "https://github.com/kyrepeak/kyre-sports-ai/pull/1222",
        "https://api.github.com/repos/kyrepeak/kyre-sports-ai/pulls/1222",
    ]
    normalized = {normalize_target(value, repository=repo) for value in variants}
    assert normalized == {"github:pr/kyrepeak/kyre-sports-ai/1222"}


def test_run_and_job_url_aliases_collapse():
    repo = "kyrepeak/kyre-sports-ai"
    assert normalize_target("run:36671107568", repository=repo) == (
        "github:run/kyrepeak/kyre-sports-ai/36671107568"
    )
    assert normalize_target(
        "https://github.com/kyrepeak/kyre-sports-ai/actions/runs/36671107568",
        repository=repo,
    ) == "github:run/kyrepeak/kyre-sports-ai/36671107568"
    assert normalize_target(
        "https://github.com/kyrepeak/kyre-sports-ai/actions/runs/36671107568/job/109746952578",
        repository=repo,
    ) == "github:job/kyrepeak/kyre-sports-ai/109746952578"


def test_branch_aliases_collapse_without_destroying_case():
    repo = "kyrepeak/kyre-sports-ai"
    a = normalize_target("refs/heads/Feature/MyBranch", repository=repo)
    b = normalize_target("branch:Feature/MyBranch", repository=repo)
    assert a == b == "github:branch/kyrepeak/kyre-sports-ai/Feature/MyBranch"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("merge pull request", "merge"),
        ("merge_pr", "merge"),
        ("workflow-dispatch", "dispatch_workflow"),
        ("poll status", "observe_async"),
        ("read_run_status", "observe_async"),
        ("open pull request", "create_pr"),
        ("branch update", "update_branch"),
    ],
)
def test_action_type_aliases_collapse(raw, expected):
    assert normalize_action_type(raw) == expected


def test_known_identity_payload_fields_are_type_stable():
    repo = "owner/repo"
    a = canonicalize_action(
        {
            "task_id": "Task",
            "checkpoint_id": "01",
            "action_type": "merge_pr",
            "target": "pr:7",
            "inputs": {
                "pr_number": "7",
                "head_sha": "A" * 40,
                "repository": "OWNER/REPO",
                "head_branch": "refs/heads/Feature/X",
            },
        },
        repository=repo,
    )
    b = canonicalize_action(
        {
            "task_id": "task",
            "checkpoint_id": 1,
            "action_type": "merge",
            "target": "https://github.com/owner/repo/pull/7",
            "inputs": {
                "pr_number": 7,
                "head_sha": "a" * 40,
                "repository": "owner/repo",
                "head_branch": "Feature/X",
            },
        },
        repository=repo,
    )
    assert a == b
    assert semantic_fingerprint(a, repository=repo) == semantic_fingerprint(b, repository=repo)


def test_different_pr_number_stays_semantically_distinct():
    repo = "owner/repo"
    base = {
        "task_id": "task",
        "checkpoint_id": "1",
        "action_type": "merge",
    }
    a = {**base, "target": "pr:7"}
    b = {**base, "target": "pr:8"}
    assert semantic_fingerprint(a, repository=repo) != semantic_fingerprint(b, repository=repo)


def test_cross_repository_pr_urls_do_not_collide():
    a = normalize_target(
        "https://github.com/owner/repo/pull/7",
        repository="owner/repo",
    )
    b = normalize_target(
        "https://github.com/other/repo/pull/7",
        repository="owner/repo",
    )
    assert a != b


def test_unknown_action_type_is_stable_but_not_misrepresented():
    assert normalize_action_type("Future Mutation") == "future_mutation"


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["alias_targets_equal"] is True
    assert result["alias_action_types_equal"] is True
    assert result["alias_payloads_equal"] is True
    assert result["semantic_fingerprints_equal"] is True
    assert result["different_action_stays_distinct"] is True
    assert result["first_alias_authorized"] is True
    assert result["second_alias_replay_skipped"] is True
    assert result["raw_step1_authority_rejected"] is True
    assert result["tampered_normalization_proof_rejected"] is True
    assert result["normalization_proof_valid"] is True
    assert result["distributed_lease_preserved"] is True
    assert result["two_a_chain_preserved"] is True
    assert result["product_runtime_mutation"] is False


def test_direct_script_execution_is_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "semantic_action_normalizer_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_V4_SEMANTIC_ACTION_NORMALIZER_V1_GREEN" in completed.stdout
