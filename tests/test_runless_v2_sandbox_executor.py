import hashlib
import json
import sys
import types
from pathlib import Path

import pytest

from runless_v2.models import FailureClass
from runless_v2.sandbox_executor import (
    SandboxExecutor,
    SandboxExecutionError,
    VercelSandboxBackend,
    validate_command,
)

SHA = "a" * 40


class FakeBackend:
    def __init__(self, *, head=SHA, plan=None, command_results=None, fail_create=None):
        self.head = head
        self.plan = plan or {
            "task_id": "task-4",
            "workstream": "ws-4",
            "commands": [["python", "-m", "pytest", "-q", "tests/example.py"]],
            "artifacts": ["artifact.py"],
            "dependencies": ["dependency.py"],
            "probes": [],
            "timeout_seconds": 120,
            "live_ttl_seconds": 900,
            "freeze_token": "TOKEN",
        }
        self.command_results = list(command_results or [
            {"exit_code": 0, "stdout": "ok\n", "stderr": ""}
        ])
        self.fail_create = fail_create
        self.created = []
        self.commands = []
        self.stopped = []

    async def create(self, **kwargs):
        if self.fail_create:
            raise self.fail_create
        self.created.append(kwargs)
        return "session-1"

    async def run(self, session_id, command, args=(), *, cwd=None, env=None, timeout_ms=None):
        self.commands.append({
            "session_id": session_id,
            "command": command,
            "args": list(args),
            "cwd": cwd,
            "env": dict(env or {}),
            "timeout_ms": timeout_ms,
        })
        if command == "git" and list(args) == ["rev-parse", "HEAD"]:
            return {"exit_code": 0, "stdout": self.head + "\n", "stderr": ""}
        if command == "python" and list(args) and list(args)[0] == "-c" and "json" in list(args)[1]:
            return {"exit_code": 0, "stdout": json.dumps(self.plan), "stderr": ""}
        result = self.command_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def stop(self, session_id):
        self.stopped.append(session_id)


def test_vercel_sdk_is_pinned_to_promoted_v2_sandbox_client():
    requirements = (Path(__file__).resolve().parents[1] / "runless_v2" / "requirements.txt").read_text()
    assert "vercel==0.12.1" in requirements.splitlines()


@pytest.mark.asyncio
async def test_vercel_backend_uses_promoted_create_sandbox_and_run_process(monkeypatch):
    calls = {"create": None, "processes": [], "stopped": 0}

    class FakeGitSource:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeCompletedProcess:
        def __init__(self, *, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    class FakeBox:
        current_session_id = "sandbox-1"

        async def run_process(
            self, command, args=None, *, cwd=None, env=None, sudo=False,
            kill_after=None, check=False, capture_output=False, **kwargs
        ):
            args = list(args or [])
            calls["processes"].append({
                "command": command,
                "args": args,
                "cwd": cwd,
                "env": dict(env or {}),
                "kill_after": kill_after,
                "capture_output": capture_output,
            })
            if command == "python" and args == ["--version"]:
                return FakeCompletedProcess(stdout="Python 3.13.1\n")
            return FakeCompletedProcess()

        async def stop(self):
            calls["stopped"] += 1

    async def fake_create_sandbox(**kwargs):
        calls["create"] = kwargs
        return FakeBox()

    fake_sandbox = types.ModuleType("vercel.sandbox")
    fake_sandbox.create_sandbox = fake_create_sandbox
    fake_sandbox.GitSource = FakeGitSource
    fake_vercel = types.ModuleType("vercel")
    fake_vercel.sandbox = fake_sandbox
    monkeypatch.setitem(sys.modules, "vercel", fake_vercel)
    monkeypatch.setitem(sys.modules, "vercel.sandbox", fake_sandbox)

    backend = VercelSandboxBackend()
    session_id = await backend.create(
        candidate_sha=SHA,
        github_token="gh-token",
        runtime="python3.13",
        persistent=False,
        timeout_ms=300_000,
    )

    assert session_id == "sandbox-1"
    assert calls["create"]["persistent"] is False
    assert calls["create"]["execution_time_limit"] == 300
    assert "runtime" not in calls["create"]
    assert "timeout" not in calls["create"]
    source = calls["create"]["source"]
    assert source.kwargs == {
        "url": "https://github.com/kyrepeak/kyre-sports-ai.git",
        "revision": SHA,
        "depth": 1,
        "username": "x-access-token",
        "password": "gh-token",
    }
    assert calls["processes"][0]["command"] == "python"
    assert calls["processes"][0]["args"] == ["--version"]
    assert calls["processes"][0]["capture_output"] is True
    assert calls["processes"][1]["args"][:4] == ["-m", "pip", "install", "--disable-pip-version-check"]

    result = await backend.run(
        session_id,
        "python",
        ["-c", "print('ok')"],
        cwd="/vercel/sandbox",
        timeout_ms=5_000,
    )
    assert result == {"exit_code": 0, "stdout": "", "stderr": ""}
    assert calls["processes"][-1]["kill_after"] == 5.0
    assert calls["processes"][-1]["capture_output"] is True

    await backend.stop(session_id)
    assert calls["stopped"] == 1


@pytest.mark.asyncio
async def test_exact_candidate_runtime_and_nonpersistent_sandbox_contract():
    backend = FakeBackend()
    result = await SandboxExecutor(backend=backend).execute(
        candidate_sha=SHA,
        task_id="task-4",
        github_token="short-lived-token",
        timeout_seconds=300,
    )
    assert result.ok is True
    assert backend.created == [{
        "candidate_sha": SHA,
        "github_token": "short-lived-token",
        "runtime": "python3.13",
        "persistent": False,
        "timeout_ms": 300000,
    }]
    assert backend.commands[0]["command"] == "git"
    assert backend.commands[0]["args"] == ["rev-parse", "HEAD"]
    assert backend.stopped == ["session-1"]


@pytest.mark.asyncio
async def test_head_mismatch_fails_closed_and_still_stops_sandbox():
    backend = FakeBackend(head="b" * 40)
    with pytest.raises(SandboxExecutionError, match="RUNLESS_V2_SANDBOX_HEAD_MISMATCH"):
        await SandboxExecutor(backend=backend).execute(
            candidate_sha=SHA, task_id="task-4", github_token="tok", timeout_seconds=100
        )
    assert backend.stopped == ["session-1"]


def test_command_allowlist_rejects_shell_metacharacters_and_unknown_modules():
    with pytest.raises(ValueError, match="RUNLESS_V2_COMMAND_REJECTED"):
        validate_command(("python", "-m", "pytest", "-q", "x.py;rm"))
    with pytest.raises(ValueError, match="RUNLESS_V2_COMMAND_REJECTED"):
        validate_command(("python", "-m", "os", "system"))
    assert validate_command(("python", "-m", "pytest", "-q", "x.py"))
    assert validate_command(("python", "-m", "devsystem.check", "--x"))
    assert validate_command(("python", "-m", "py_compile", "devsystem/x.py"))


@pytest.mark.asyncio
async def test_plan_with_rejected_command_fails_before_execution_and_cleans_up():
    plan = {
        "task_id": "task-4",
        "workstream": "ws-4",
        "commands": [["python", "-m", "pytest", "x.py && echo bad"]],
        "artifacts": [], "dependencies": [], "probes": [],
        "timeout_seconds": 60, "live_ttl_seconds": 60, "freeze_token": "T",
    }
    backend = FakeBackend(plan=plan)
    with pytest.raises(SandboxExecutionError, match="RUNLESS_V2_COMMAND_REJECTED"):
        await SandboxExecutor(backend=backend).execute(
            candidate_sha=SHA, task_id="task-4", github_token="tok", timeout_seconds=100
        )
    assert len(backend.commands) == 2
    assert backend.stopped == ["session-1"]


@pytest.mark.asyncio
async def test_static_failure_returns_hashed_evidence_without_raw_output():
    backend = FakeBackend(command_results=[
        {"exit_code": 1, "stdout": "secret-ish stdout", "stderr": "assertion failed"}
    ])
    result = await SandboxExecutor(backend=backend).execute(
        candidate_sha=SHA, task_id="task-4", github_token="tok", timeout_seconds=100
    )
    evidence = result.evidence[0]
    assert result.ok is False
    assert evidence.failure_class is FailureClass.STATIC_PROOF
    assert evidence.stdout_digest == hashlib.sha256(b"secret-ish stdout").hexdigest()
    assert evidence.stderr_digest == hashlib.sha256(b"assertion failed").hexdigest()
    assert "secret-ish stdout" not in result.model_dump_json()
    assert "assertion failed" not in result.model_dump_json()
    assert backend.stopped == ["session-1"]


@pytest.mark.asyncio
async def test_timeout_is_infra_failure_and_no_retry_occurs():
    backend = FakeBackend(command_results=[TimeoutError("timed out")])
    result = await SandboxExecutor(backend=backend).execute(
        candidate_sha=SHA, task_id="task-4", github_token="tok", timeout_seconds=100
    )
    assert result.ok is False
    assert result.evidence[0].failure_class is FailureClass.INFRA
    assert result.evidence[0].detail == "RUNLESS_V2_SANDBOX_COMMAND_TIMEOUT"
    proof_commands = [item for item in backend.commands if item["command"] == "python" and not (item["args"] and item["args"][0] == "-c" and "json" in item["args"][1])]
    assert len(proof_commands) == 1
    assert backend.stopped == ["session-1"]


@pytest.mark.asyncio
async def test_backend_create_failure_does_not_attempt_stop_without_session():
    backend = FakeBackend(fail_create=RuntimeError("unavailable"))
    with pytest.raises(SandboxExecutionError, match=r"^RUNLESS_V2_SANDBOX_CREATE_FAILED:RuntimeError$"):
        await SandboxExecutor(backend=backend).execute(
            candidate_sha=SHA, task_id="task-4", github_token="tok", timeout_seconds=100
        )
    assert backend.stopped == []
