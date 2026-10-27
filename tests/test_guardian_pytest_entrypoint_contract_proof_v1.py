from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "runless_v2" / "guardian_pytest_entrypoint_contract_proof_v1.py"
BOOTSTRAP = ROOT / "runless_v2" / "guardian_freeze_closeout_bootstrap_v1.py"
PLAN = ROOT / "devsystem" / "runless_proof_plans" / "guardian-pytest-entrypoint-contract-v1.json"

TASK_ID = "guardian-pytest-entrypoint-contract-v1"
BRANCH = TASK_ID
EXPECTED_MAIN_SHA = "f0305b6d62b979c32412c1d54ec16ec9e4652e4f"


def _load_proof():
    assert PROOF.is_file(), "Guardian pytest entrypoint proof publisher is missing"
    spec = importlib.util.spec_from_file_location("guardian_pytest_entrypoint_contract_proof_v1", PROOF)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_guardian_pytest_entrypoint_proof_assets_exist():
    assert PROOF.is_file()
    assert PLAN.is_file()


def test_guardian_pytest_entrypoint_proof_identity_is_exact_and_independent():
    proof = _load_proof()
    assert proof.AUTHORITY == "KYRE_GUARDIAN_ONLY"
    assert proof.TASK_ID == TASK_ID and proof.WORKSTREAM == TASK_ID
    assert proof.PR_NUMBER == 1901
    assert proof.BRANCH == BRANCH
    assert proof.BASE_BRANCH == "main"
    assert proof.EXPECTED_MAIN_SHA == EXPECTED_MAIN_SHA
    assert proof.GATE_NAME == "runless-final-gate"
    assert proof.GITHUB_APP_ID == "5204253"


def test_guardian_pytest_entrypoint_plan_is_exact_and_foreign_state_free():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert plan["mode"] == "runless"
    assert plan["task_id"] == TASK_ID and plan["workstream"] == TASK_ID
    assert plan["source_main_sha"] == EXPECTED_MAIN_SHA
    assert plan["required_check"] == "runless-final-gate"
    assert plan["required_check_app_id"] == 5204253
    assert plan["github_actions_fallback"] == 0
    assert plan["freeze_token"] == "GUARDIAN_PYTEST_ENTRYPOINT_CONTRACT_V1_FROZEN"
    joined = " ".join([*plan.get("artifacts", []), *plan.get("dependencies", [])]).lower()
    assert "task_ledgers/api2" not in joined
    assert "task_ledgers/monster" not in joined
    assert "frozen_artifact_registry" not in joined


def test_guardian_pytest_entrypoint_bootstrap_is_branch_scoped():
    source = BOOTSTRAP.read_text(encoding="utf-8")
    assert 'PYTEST_ENTRYPOINT_BRANCH = "guardian-pytest-entrypoint-contract-v1"' in source
    assert "_prove_pytest_entrypoint" in source
    assert "GUARDIAN_PYTEST_ENTRYPOINT_AUTO_PROOF" in source


def test_guardian_pytest_entrypoint_proof_rejects_foreign_private_state():
    source = PROOF.read_text(encoding="utf-8") if PROOF.exists() else ""
    assert "MONSTER_ONLY" not in source
    assert "API2_ONLY" not in source
    assert "task_ledgers/monster" not in source
    assert "task_ledgers/api2" not in source
    assert "frozen_artifact_registry" not in source
