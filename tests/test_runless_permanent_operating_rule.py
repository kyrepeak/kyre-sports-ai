from pathlib import Path
import inspect
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_normal_proof_code_exposes_no_actions_dispatch_or_rerun_api():
    from runless_proof_plane.github_client import GithubClient
    source = inspect.getsource(GithubClient).lower()
    forbidden = (
        "/actions/workflows/",
        "/actions/runs/",
        "dispatches",
        "rerun",
        "rerun-failed-jobs",
    )
    for token in forbidden:
        assert token not in source
    assert not hasattr(GithubClient, "dispatch_workflow")
    assert not hasattr(GithubClient, "rerun_workflow")


def test_missing_runless_plan_fails_closed_without_actions_fallback(tmp_path):
    from devsystem.runless_proof_plan_v1 import RunlessPlanRequired, load_plan
    with pytest.raises(RunlessPlanRequired, match="RUNLESS_PLAN_REQUIRED"):
        load_plan("missing-task", tmp_path)


def test_legacy_actions_fallback_requires_explicit_kyre_authorization():
    from devsystem.runless_actions_fallback_policy_v1 import authorize_manual_actions_fallback
    assert authorize_manual_actions_fallback(None).authorized is False
    assert authorize_manual_actions_fallback("").authorized is False
    assert authorize_manual_actions_fallback("someone-else").authorized is False
    assert authorize_manual_actions_fallback("KYRE_EXPLICIT_AUTHORIZATION").authorized is True


def test_green_frozen_impossible_without_exact_registry_readback():
    from runless_proof_plane.registry import FreezeWrite, FreezeReadback, can_claim_green_frozen
    write = FreezeWrite(
        token="WNBA_PRA_REPAIR_V1_STEP3_FROZEN",
        merged_sha="a" * 40,
        revision=127,
        state_hash="b" * 64,
        receipt_digest="c" * 64,
    )
    assert can_claim_green_frozen(write, None) is False
    mismatch = FreezeReadback(
        token=write.token,
        merged_sha=write.merged_sha,
        revision=128,
        state_hash=write.state_hash,
        receipt_digest=write.receipt_digest,
    )
    assert can_claim_green_frozen(write, mismatch) is False
    exact = FreezeReadback(**write.__dict__)
    assert can_claim_green_frozen(write, exact) is True


def test_operations_doc_covers_required_runbook_topics():
    text = (ROOT / "docs" / "runless-proof-plane-operations.md").read_text(encoding="utf-8").lower()
    for term in (
        "health",
        "proof submission",
        "wait",
        "failure class",
        "receipt lookup",
        "restart",
        "github app rotation",
        "render outage",
        "emergency fallback",
        "explicit kyre authorization",
        "registry read-back",
    ):
        assert term in text


def test_required_permanent_rule_is_literal_and_frozen():
    from runless_proof_plane.permanent_rule import PERMANENT_OPERATING_RULE
    assert PERMANENT_OPERATING_RULE == (
        "API 2 / MONSTER GREEN + FROZEN must not depend on GitHub Actions. "
        "Normal proof executes through the Runless Proof Plane. GitHub receives proof status only. "
        "GitHub Actions is a manual emergency fallback and may run only with explicit Kyre authorization."
    )
