from __future__ import annotations

from devsystem.content_addressed_proof_reuse_ci_v1 import (
    TARGET_WORKFLOW_NAME,
    contract_self_test,
    discover_parent_terminal_proof,
    parse_ls_tree,
    policy_dependency_map,
    protected_blob_map,
)

A = "a" * 40
B = "b" * 40
C = "c" * 40
DIGEST = "sha256:" + "d" * 64


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["control_plane_excluded"] is True
    assert result["product_surface_protected"] is True
    assert result["workflow_surface_protected"] is True
    assert result["network_is_read_only"] is True
    assert result["product_runtime_mutation"] is False
    assert result["mutation_authority_granted"] is False


def test_protected_blob_map_excludes_only_control_plane_surfaces():
    rows = "\n".join(
        [
            f"100644 blob {A}\tdevsystem/x.py",
            f"100644 blob {A}\ttests/test_devsystem_x.py",
            f"100644 blob {A}\tdocs/x.md",
            f"100644 blob {B}\twnba_page.py",
            f"100644 blob {C}\ttests/test_cfb_schedule.py",
            f"100644 blob {B}\t.github/workflows/devsystem-targeted-ci.yml",
        ]
    )
    protected = protected_blob_map(parse_ls_tree(rows))
    assert "devsystem/x.py" not in protected
    assert "tests/test_devsystem_x.py" not in protected
    assert "docs/x.md" not in protected
    assert protected["wnba_page.py"] == B
    assert protected["tests/test_cfb_schedule.py"] == C
    assert ".github/workflows/devsystem-targeted-ci.yml" in protected


def test_policy_dependency_map_fails_closed_if_adapter_is_missing():
    tree = {
        ".github/workflows/devsystem-targeted-ci.yml": A,
        "devsystem/change_classifier_v1.py": A,
        "devsystem/content_addressed_proof_reuse_v1.py": A,
        "devsystem/permanent_gate_v1.py": A,
    }
    try:
        policy_dependency_map(tree)
    except Exception as exc:
        assert "content_addressed_proof_reuse_ci_v1.py" in str(exc)
    else:
        raise AssertionError("missing CI adapter dependency must fail closed")


def test_parent_terminal_proof_discovery_requires_exact_success_and_receipt():
    calls = []

    def fake_api(url: str, auth_value: str):
        calls.append((url, auth_value))
        if "/actions/runs?" in url:
            return {
                "workflow_runs": [
                    {
                        "id": 10,
                        "name": TARGET_WORKFLOW_NAME,
                        "event": "push",
                        "head_sha": A,
                        "conclusion": "failure",
                        "run_number": 9,
                    },
                    {
                        "id": 11,
                        "name": TARGET_WORKFLOW_NAME,
                        "event": "push",
                        "head_sha": A,
                        "conclusion": "success",
                        "run_number": 10,
                    },
                ]
            }
        return {
            "artifacts": [
                {
                    "id": 99,
                    "name": "monster-v4-step5-terminal-proof-11",
                    "expired": False,
                    "digest": DIGEST,
                    "workflow_run": {"head_sha": A},
                }
            ]
        }

    proof = discover_parent_terminal_proof(
        repository="owner/repo",
        base_sha=A,
        token="x",
        api_json=fake_api,
    )
    assert proof == {
        "run_id": 11,
        "terminal_receipt_digest": DIGEST,
        "artifact_id": 99,
        "head_sha": A,
    }
    assert len(calls) == 2


def test_parent_proof_missing_or_expired_fails_closed():
    def fake_api(url: str, auth_value: str):
        if "/actions/runs?" in url:
            return {
                "workflow_runs": [
                    {
                        "id": 11,
                        "name": TARGET_WORKFLOW_NAME,
                        "event": "push",
                        "head_sha": A,
                        "conclusion": "success",
                        "run_number": 10,
                    }
                ]
            }
        return {
            "artifacts": [
                {
                    "id": 99,
                    "name": "monster-v4-step5-terminal-proof-11",
                    "expired": True,
                    "digest": DIGEST,
                    "workflow_run": {"head_sha": A},
                }
            ]
        }

    assert discover_parent_terminal_proof(
        repository="owner/repo",
        base_sha=A,
        token="x",
        api_json=fake_api,
    ) is None
