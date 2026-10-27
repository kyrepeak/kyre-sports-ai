from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "guardian-shared-runtime-lifecycle-freeze-closeout-v1"


def _load_sandbox_executor():
    package_name = "_guardian_cleanup_runless_v2"
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
        "freeze_token": "GUARDIAN_SHARED_RUNTIME_LIFECYCLE_FREEZE_CLOSEOUT_V1_FROZEN",
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
            return {"exit_code": 0, "stdout": "proof green\n", "stderr": ""}

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
