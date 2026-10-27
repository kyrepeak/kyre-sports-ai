from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "runless_v2" / "guardian_monster_freeze_idempotency_proof_v1.py"
PLAN = ROOT / "devsystem" / "runless_proof_plans" / "guardian-monster-freeze-idempotency-v1.json"
BOOTSTRAP = ROOT / "runless_v2" / "guardian_freeze_closeout_bootstrap_v1.py"

TASK_ID = "guardian-monster-freeze-idempotency-v1"
BRANCH = TASK_ID
EXPECTED_MAIN_SHA = "afc8387dea50ae1e683fdc9e97307f83e6e4f846"


def _load_proof():
    assert PROOF.is_file(), "Guardian freeze-idempotency Runless proof publisher is missing"
    spec = importlib.util.spec_from_file_location("guardian_monster_freeze_idempotency_proof_v1", PROOF)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_freeze_idempotency_runless_proof_module_and_plan_exist():
    assert PROOF.is_file(), "Guardian freeze-idempotency Runless proof publisher is missing"
    assert PLAN.is_file(), "Guardian freeze-idempotency Runless proof plan is missing"


def test_freeze_idempotency_proof_identity_is_exact_and_guardian_only():
    proof = _load_proof()
    assert proof.AUTHORITY == "KYRE_GUARDIAN_ONLY"
    assert proof.TASK_ID == TASK_ID
    assert proof.WORKSTREAM == TASK_ID
    assert proof.PR_NUMBER == 1899
    assert proof.BRANCH == BRANCH
    assert proof.BASE_BRANCH == "main"
    assert proof.EXPECTED_MAIN_SHA == EXPECTED_MAIN_SHA
    assert proof.GATE_NAME == "runless-final-gate"
    assert proof.GITHUB_APP_ID == "5204253"


def test_freeze_idempotency_plan_is_exact_head_runless_only():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert plan["mode"] == "runless"
    assert plan["task_id"] == TASK_ID
    assert plan["workstream"] == TASK_ID
    assert plan["source_main_sha"] == EXPECTED_MAIN_SHA
    assert plan["github_actions_fallback"] == 0
    assert plan["required_check"] == "runless-final-gate"
    assert plan["required_check_app_id"] == 5204253
    assert plan["freeze_token"] == "GUARDIAN_MONSTER_FREEZE_IDEMPOTENCY_V1_FROZEN"
    joined = " ".join([*plan.get("artifacts", []), *plan.get("dependencies", [])]).lower()
    assert "task_ledgers/api2" not in joined
    assert "task_ledgers/monster" not in joined
    assert "frozen_artifact_registry_state_v1.json" not in joined


def test_existing_guardian_bootstrap_registers_exact_new_branch_without_foreign_state():
    source = BOOTSTRAP.read_text(encoding="utf-8")
    assert BRANCH in source
    assert "guardian_monster_freeze_idempotency_proof_v1" in source
    assert "GUARDIAN_MONSTER_FREEZE_IDEMPOTENCY_AUTO_PROOF_GREEN" in source
    assert "RUNLESS_PROOF_AUTH_TOKEN" not in source
