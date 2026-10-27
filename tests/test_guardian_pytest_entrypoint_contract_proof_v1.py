from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "runless_v2" / "guardian_pytest_entrypoint_contract_proof_v1.py"
BOOTSTRAP = ROOT / "runless_v2" / "guardian_freeze_closeout_bootstrap_v1.py"
PLAN = ROOT / "devsystem" / "runless_proof_plans" / "guardian-pytest-entrypoint-contract-v1.json"
TERMINAL_QA = ROOT / "devsystem" / "guardian_cfb_game_total_terminal_browser_qa_v1.py"
BROWSER_WORKFLOW = ROOT / ".github" / "workflows" / "cfb-game-total-v150-browser.yml"
ACTIVATION_WORKFLOW = ROOT / ".github" / "workflows" / "cfb-game-total-v152-activation.yml"

TASK_ID = "guardian-pytest-entrypoint-contract-v1"
BRANCH = TASK_ID
EXPECTED_MAIN_SHA = "f0305b6d62b979c32412c1d54ec16ec9e4652e4f"


def _load_proof():
    assert PROOF.is_file(), "Guardian pytest entrypoint proof publisher is missing"
    spec = importlib.util.spec_from_file_location(
        "guardian_pytest_entrypoint_contract_proof_v1",
        PROOF,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


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


def test_step2a_scope_is_exact_and_matches_runless_artifacts():
    proof = _load_proof()
    plan = _plan()
    assert set(plan["artifacts"]) == set(proof.ALLOWED_CHANGED_PATHS)
    assert len(proof.ALLOWED_CHANGED_PATHS) == 10
    joined = " ".join(sorted(proof.ALLOWED_CHANGED_PATHS))
    for frozen_product_path in (
        "devsystem/cfb_game_total_browser_qa_v4.py",
        "devsystem/cfb_game_total_step6_browser_qa_v184.py",
        "tests/test_cfb_game_total_v163_game_selector.py",
        "tests/test_cfb_game_total_v184_step6_scoring.py",
        "tests/test_cfb_game_total_v185_step6_visual_parity.py",
    ):
        assert frozen_product_path not in proof.ALLOWED_CHANGED_PATHS
    assert "task_ledgers/api2" not in joined.lower()
    assert "task_ledgers/monster" not in joined.lower()
    assert "frozen_artifact_registry" not in joined.lower()


def test_guardian_runless_plan_uses_one_current_terminal_contract():
    plan = _plan()
    assert plan["mode"] == "runless"
    assert plan["task_id"] == TASK_ID and plan["workstream"] == TASK_ID
    assert plan["source_main_sha"] == EXPECTED_MAIN_SHA
    assert plan["required_check"] == "runless-final-gate"
    assert plan["required_check_app_id"] == 5204253
    assert plan["github_actions_fallback"] == 0
    assert plan["freeze_token"] == "GUARDIAN_PYTEST_ENTRYPOINT_CONTRACT_V1_FROZEN"
    commands = " ".join(" ".join(command) for command in plan["commands"])
    assert "tests/test_guardian_cfb_game_total_terminal_browser_qa_v1.py" in commands
    assert "tests/test_cfb_game_total_v163_game_selector.py" in commands
    assert "tests/test_cfb_game_total_v184_step6_browser.py" not in commands


def test_guardian_pytest_entrypoint_bootstrap_is_branch_scoped():
    source = BOOTSTRAP.read_text(encoding="utf-8")
    assert 'PYTEST_ENTRYPOINT_BRANCH = "guardian-pytest-entrypoint-contract-v1"' in source
    assert "_prove_pytest_entrypoint" in source
    assert "GUARDIAN_PYTEST_ENTRYPOINT_AUTO_PROOF" in source


def test_unavoidable_browser_wrappers_share_one_terminal_qa_owner():
    assert TERMINAL_QA.is_file()
    command = "python -m devsystem.guardian_cfb_game_total_terminal_browser_qa_v1"
    for workflow_path in (BROWSER_WORKFLOW, ACTIVATION_WORKFLOW):
        workflow = workflow_path.read_text(encoding="utf-8")
        assert command in workflow
        assert "python -m devsystem.cfb_game_total_browser_qa_v4" not in workflow
    source = TERMINAL_QA.read_text(encoding="utf-8")
    assert "fixed_historical_date_required" in source
    assert '"historical_surface_required": False' in source
