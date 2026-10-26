from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "runless_v2" / "monster_nba_pra_page1_history_batching_proof_r2.py"
INIT = ROOT / "runless_v2" / "__init__.py"
PLAN = ROOT / "devsystem" / "runless_proof_plans" / "monster-nba-pra-page1-history-batching-r2.json"


def _load_proof():
    spec = importlib.util.spec_from_file_location("monster_nba_pra_page1_history_batching_proof_r2_test", PROOF)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r2_proof_identity_is_monster_only():
    proof = _load_proof()
    assert proof.AUTHORITY == "MONSTER_ONLY"
    assert proof.TASK_ID == "monster-nba-pra-page1-history-batching-r2"
    assert proof.WORKSTREAM == proof.TASK_ID
    assert proof.PR_NUMBER == 1878
    assert proof.BRANCH == "monster-nba-pra-page1-history-batching-r2"
    assert proof.EXPECTED_MAIN_SHA == "fcb158850dc55486113780c7cee27da8725e2379"
    assert proof.GITHUB_APP_ID == "5204253"
    assert proof.RECEIPT_REF == "monster-step2g-proof-receipts-v1"


def test_r2_receipt_rejects_foreign_system_evidence():
    proof = _load_proof()
    plan = {"task_id": proof.TASK_ID, "workstream": proof.WORKSTREAM, "source_main_sha": proof.EXPECTED_MAIN_SHA}
    with pytest.raises(proof.MonsterNbaPraBatchingProofFailure, match="FOREIGN_SYSTEM_EVIDENCE_FORBIDDEN"):
        proof.build_receipt(
            candidate_sha="b" * 40,
            expected_main_sha=proof.EXPECTED_MAIN_SHA,
            changed_paths=sorted(proof.ALLOWED_CHANGED_PATHS),
            artifact_map={path: "a" * 40 for path in proof.ALLOWED_CHANGED_PATHS},
            dependency_map={},
            evidence=[{"ok": True, "source": "API 2"}],
            plan=plan,
        )


def test_r2_proof_does_not_consume_shared_control_state():
    text = PROOF.read_text(encoding="utf-8").casefold()
    for forbidden in (
        "monster-frozen-artifact-registry",
        "api2-scope-aware-execution-leases",
        "api2-finalization-ledger-v2",
        "runless_v2.proof_runs",
        "supabase",
        "scope_lease_id",
    ):
        assert forbidden.casefold() not in text
    assert "monster_only" in text
    assert "monster-step2g-proof-receipts-v1" in text


def test_r2_preview_hook_is_exact_branch_only():
    text = INIT.read_text(encoding="utf-8")
    assert "_monster_nba_pra_page1_history_batching_maybe_auto_prove" in text
    assert 'authorized_branch = "monster-nba-pra-page1-history-batching-r2"' in text
    assert "monster_nba_pra_page1_history_batching_proof_r2" in text


def test_r2_plan_proves_product_and_isolation_contracts():
    import json

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    flat = "\n".join(" ".join(map(str, command)) for command in (plan.get("commands") or []))
    assert "test_monster_nba_pra_page1_history_batching_r2.py" in flat
    assert "test_monster_nba_pra_page1_history_batching_proof_r2.py" in flat
    artifacts = plan.get("artifacts") or []
    assert "runless_v2/monster_nba_pra_page1_history_batching_proof_r2.py" in artifacts
    assert "runless_v2/__init__.py" in artifacts
