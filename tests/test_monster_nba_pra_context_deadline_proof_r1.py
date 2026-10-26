from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "runless_v2" / "monster_nba_pra_context_deadline_proof_r1.py"
INIT = ROOT / "runless_v2" / "__init__.py"
PLAN = ROOT / "devsystem" / "runless_proof_plans" / "monster-nba-pra-context-deadline-r1.json"


def _load_proof():
    spec = importlib.util.spec_from_file_location("monster_nba_pra_context_deadline_proof_r1_test", PROOF)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_monster_proof_identity_is_hard_isolated():
    proof = _load_proof()
    assert proof.AUTHORITY == "MONSTER_ONLY"
    assert proof.TASK_ID == "monster-nba-pra-context-deadline-r1"
    assert proof.WORKSTREAM == proof.TASK_ID
    assert proof.PR_NUMBER == 1877
    assert proof.BRANCH == "monster-nba-pra-context-deadline-r1"
    assert proof.EXPECTED_MAIN_SHA == "0fce8407d027651224665e413c42aa556565b3ae"
    assert proof.GITHUB_APP_ID == "5204253"
    assert proof.RECEIPT_REF == "monster-step2g-proof-receipts-v1"
    assert proof.RECEIPT_DIR == "devsystem/monster_step2g_proof_receipts"


def test_monster_receipt_rejects_foreign_system_evidence():
    proof = _load_proof()
    plan = {
        "task_id": proof.TASK_ID,
        "workstream": proof.WORKSTREAM,
        "source_main_sha": proof.EXPECTED_MAIN_SHA,
    }
    artifact_map = {path: "a" * 40 for path in sorted(proof.ALLOWED_CHANGED_PATHS)}
    with pytest.raises(proof.MonsterNbaPraProofFailure, match="FOREIGN_SYSTEM_EVIDENCE_FORBIDDEN"):
        proof.build_receipt(
            candidate_sha="b" * 40,
            expected_main_sha=proof.EXPECTED_MAIN_SHA,
            changed_paths=sorted(proof.ALLOWED_CHANGED_PATHS),
            artifact_map=artifact_map,
            dependency_map={},
            evidence=[{"ok": True, "source": "API 2"}],
            plan=plan,
        )


def test_monster_proof_source_never_consumes_shared_control_state():
    text = PROOF.read_text(encoding="utf-8")
    lowered = text.casefold()
    for forbidden in (
        "monster-frozen-artifact-registry",
        "api2-scope-aware-execution-leases",
        "api2-finalization-ledger-v2",
        "runless_v2.proof_runs",
        "supabase",
        "scope_lease_id",
    ):
        assert forbidden.casefold() not in lowered
    assert "MONSTER_ONLY" in text
    assert "monster-step2g-proof-receipts-v1" in text


def test_preview_hook_is_bound_only_to_current_monster_branch():
    text = INIT.read_text(encoding="utf-8")
    assert "_monster_nba_pra_context_deadline_maybe_auto_prove" in text
    assert 'authorized_branch = "monster-nba-pra-context-deadline-r1"' in text
    assert "monster_nba_pra_context_deadline_proof_r1" in text


def test_runless_plan_executes_both_product_and_isolation_contracts():
    import json

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    commands = plan.get("commands") or []
    flat = "\n".join(" ".join(map(str, command)) for command in commands)
    assert "test_monster_nba_pra_context_deadline_r1.py" in flat
    assert "test_monster_nba_pra_context_deadline_proof_r1.py" in flat
    assert "runless_v2/monster_nba_pra_context_deadline_proof_r1.py" in (plan.get("artifacts") or [])
    assert "runless_v2/__init__.py" in (plan.get("artifacts") or [])
