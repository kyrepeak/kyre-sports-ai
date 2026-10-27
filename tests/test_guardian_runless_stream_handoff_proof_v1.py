from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "runless_v2" / "guardian_runless_stream_handoff_proof_v1.py"
BOOTSTRAP = ROOT / "runless_v2" / "guardian_freeze_closeout_bootstrap_v1.py"
PLAN = ROOT / "devsystem" / "runless_proof_plans" / "guardian-runless-stream-handoff-v1.json"

TASK_ID = "guardian-runless-stream-handoff-v1"
BRANCH = "guardian-runless-stream-handoff-v1"
EXPECTED_MAIN_SHA = "44b26457c874124283c44cf02713ecc847b8dfcc"


def _load_proof():
    assert PROOF.is_file(), "Guardian stream-handoff proof publisher is missing"
    spec = importlib.util.spec_from_file_location("guardian_runless_stream_handoff_proof_v1", PROOF)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_guardian_stream_handoff_proof_assets_exist():
    assert PROOF.is_file()
    assert PLAN.is_file()


def test_guardian_stream_handoff_proof_identity_is_exact_and_independent():
    proof = _load_proof()
    assert proof.AUTHORITY == "KYRE_GUARDIAN_ONLY"
    assert proof.TASK_ID == TASK_ID and proof.WORKSTREAM == TASK_ID
    assert proof.PR_NUMBER == 1900
    assert proof.BRANCH == BRANCH
    assert proof.BASE_BRANCH == "main"
    assert proof.EXPECTED_MAIN_SHA == EXPECTED_MAIN_SHA
    assert proof.GATE_NAME == "runless-final-gate"
    assert proof.GITHUB_APP_ID == "5204253"


def test_guardian_stream_handoff_plan_is_exact_head_and_foreign_state_free():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert plan["mode"] == "runless"
    assert plan["task_id"] == TASK_ID and plan["workstream"] == TASK_ID
    assert plan["source_main_sha"] == EXPECTED_MAIN_SHA
    assert plan["required_check"] == "runless-final-gate"
    assert plan["required_check_app_id"] == 5204253
    assert plan["github_actions_fallback"] == 0
    assert plan["freeze_token"] == "GUARDIAN_RUNLESS_STREAM_HANDOFF_V1_FROZEN"
    joined = " ".join([*plan.get("artifacts", []), *plan.get("dependencies", [])]).lower()
    assert "task_ledgers/api2" not in joined
    assert "task_ledgers/monster" not in joined
    assert "frozen_artifact_registry" not in joined


def test_guardian_stream_handoff_bootstrap_is_branch_scoped():
    source = BOOTSTRAP.read_text(encoding="utf-8")
    assert 'STREAM_HANDOFF_BRANCH = "guardian-runless-stream-handoff-v1"' in source
    assert "_prove_stream_handoff" in source
    assert "GUARDIAN_RUNLESS_STREAM_HANDOFF_AUTO_PROOF" in source


def test_guardian_stream_handoff_proof_rejects_foreign_private_state():
    source = PROOF.read_text(encoding="utf-8") if PROOF.exists() else ""
    assert "MONSTER_ONLY" not in source
    assert "API2_ONLY" not in source
    assert "task_ledgers/monster" not in source
    assert "task_ledgers/api2" not in source
    assert "frozen_artifact_registry" not in source
