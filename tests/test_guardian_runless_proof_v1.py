from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "runless_v2" / "guardian_shared_runtime_lifecycle_proof_v1.py"
PLAN = ROOT / "devsystem" / "runless_proof_plans" / "guardian-shared-runtime-lifecycle-v1.json"
RUNLESS_INIT = ROOT / "runless_v2" / "__init__.py"

TASK_ID = "guardian-shared-runtime-lifecycle-v1"
BRANCH = "guardian-shared-runtime-lifecycle-v1"
EXPECTED_MAIN_SHA = "49ee15d2ba9d583373e8981352eac9809cd189d0"


def _load_proof():
    assert PROOF.is_file(), "Guardian Runless proof publisher is missing"
    spec = importlib.util.spec_from_file_location("guardian_shared_runtime_lifecycle_proof_v1", PROOF)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_sandbox_executor():
    package_name = "_guardian_runless_v2"
    root = ROOT / "runless_v2"
    package = types.ModuleType(package_name)
    package.__path__ = [str(root)]
    sys.modules[package_name] = package

    for module_name in ("models", "sandbox_executor"):
        fq_name = f"{package_name}.{module_name}"
        spec = importlib.util.spec_from_file_location(fq_name, root / f"{module_name}.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[fq_name] = module
        spec.loader.exec_module(module)
    return sys.modules[f"{package_name}.sandbox_executor"]


def test_guardian_runless_proof_publisher_and_plan_exist():
    assert PROOF.is_file(), "Guardian Runless proof publisher is missing"
    assert PLAN.is_file(), "Guardian Runless proof plan is missing"


def test_guardian_proof_identity_is_exact_and_independent():
    proof = _load_proof()
    assert proof.AUTHORITY == "KYRE_GUARDIAN_ONLY"
    assert proof.TASK_ID == TASK_ID and proof.WORKSTREAM == TASK_ID
    assert proof.PR_NUMBER == 1897
    assert proof.BRANCH == BRANCH
    assert proof.BASE_BRANCH == "main"
    assert proof.EXPECTED_MAIN_SHA == EXPECTED_MAIN_SHA
    assert proof.GATE_NAME == "runless-final-gate"
    assert proof.GITHUB_APP_ID == "5204253"
    assert "runless_v2/sandbox_executor.py" in proof.ALLOWED_CHANGED_PATHS


def test_guardian_plan_is_runless_exact_head_and_has_no_foreign_private_state():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert plan["mode"] == "runless"
    assert plan["task_id"] == TASK_ID and plan["workstream"] == TASK_ID
    assert plan["source_main_sha"] == EXPECTED_MAIN_SHA
    assert plan["required_check"] == "runless-final-gate"
    assert plan["required_check_app_id"] == 5204253
    assert plan["github_actions_fallback"] == 0
    assert plan["freeze_token"] == "GUARDIAN_SHARED_RUNTIME_LIFECYCLE_V1_FROZEN"
    assert "runless_v2/sandbox_executor.py" in plan["artifacts"]
    joined = " ".join([*plan.get("artifacts", []), *plan.get("dependencies", [])]).lower()
    assert "task_ledgers/api2" not in joined
    assert "task_ledgers/monster" not in joined
    assert "monster_step2g_proof_receipts" not in joined
    assert "frozen_artifact_registry" not in joined


def test_guardian_proof_source_rejects_foreign_authority_imports():
    source = PROOF.read_text(encoding="utf-8") if PROOF.exists() else ""
    assert "MONSTER_ONLY" not in source
    assert "API2_ONLY" not in source
    assert "task_ledgers/monster" not in source
    assert "task_ledgers/api2" not in source
    assert "frozen_artifact_registry" not in source


def test_runless_preview_auto_proof_is_exact_guardian_branch_only():
    source = RUNLESS_INIT.read_text(encoding="utf-8")
    assert "_guardian_shared_runtime_lifecycle_maybe_auto_prove" in source
    assert BRANCH in source
    assert "prove_guardian_shared_runtime_lifecycle" in source
    assert "GUARDIAN_SHARED_RUNTIME_AUTO_PROOF_GREEN" in source


def test_green_sandbox_evidence_survives_cleanup_stop_error():
    SandboxExecutor = _load_sandbox_executor().SandboxExecutor

    candidate = "a" * 40
    plan = {
        "task_id": TASK_ID,
        "workstream": TASK_ID,
        "commands": [["python", "-m", "pytest", "--noconftest", "-q", "tests/example.py"]],
        "artifacts": [],
        "dependencies": [],
        "probes": [],
        "timeout_seconds": 60,
        "live_ttl_seconds": 120,
        "freeze_token": "GUARDIAN_SHARED_RUNTIME_LIFECYCLE_V1_FROZEN",
    }

    class CleanupErrorBackend:
        def __init__(self):
            self.stopped: list[str] = []

        async def create(self, **kwargs):
            return "guardian-session"

        async def run(self, session_id, command, args=(), *, cwd=None, env=None, timeout_ms=None):
            argv = list(args)
            if command == "git" and argv == ["rev-parse", "HEAD"]:
                return {"exit_code": 0, "stdout": candidate + "\n", "stderr": ""}
            if command == "python" and argv and argv[0] == "-c":
                return {"exit_code": 0, "stdout": json.dumps(plan), "stderr": ""}
            return {"exit_code": 0, "stdout": "46 passed\n", "stderr": ""}

        async def stop(self, session_id):
            self.stopped.append(session_id)
            raise RuntimeError("sandbox already stopped after successful proof")

    async def _exercise():
        backend = CleanupErrorBackend()
        result = await SandboxExecutor(backend=backend).execute(
            candidate_sha=candidate,
            task_id=TASK_ID,
            github_token="short-lived-token",
            timeout_seconds=60,
        )
        return backend, result

    backend, result = asyncio.run(_exercise())
    assert result.ok is True
    assert backend.stopped == ["guardian-session"]
