from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field

from .models import FailureClass

_BAD_SHELL = re.compile(r"[;&|><`$\n\r]")
_APPROVED_MODULE_PREFIXES = ("devsystem.",)
_MAX_SANDBOX_SECONDS = 1800
_MIN_BOOTSTRAP_PACKAGES = (
    "pytest",
    "pytest-asyncio",
    "fastapi",
    "httpx",
    "requests",
    "pypdf",
    "PyJWT",
    "cryptography",
    "pandas",
    "numpy",
    "streamlit",
)
_REPOSITORY_URL = "https://github.com/kyrepeak/kyre-sports-ai.git"


class SandboxExecutionError(RuntimeError):
    pass


def _classify_proof_command_failure(stdout: str, stderr: str) -> tuple[FailureClass, str]:
    text = f"{stdout}\n{stderr}".lower()
    missing_dependency = (
        "modulenotfounderror" in text
        or "no module named" in text
        or (
            "importerror" in text
            and any(
                marker in text
                for marker in (
                    "missing optional dependency",
                    "required dependency",
                    "is not installed",
                    "package is required",
                )
            )
        )
    )
    if missing_dependency:
        return FailureClass.INFRA, "RUNLESS_V2_PROOF_ENVIRONMENT_DEPENDENCY_MISSING"
    return FailureClass.STATIC_PROOF, "RUNLESS_V2_STATIC_PROOF_FAILED"


def validate_command(command: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    cmd = tuple(str(part) for part in command)
    text = " ".join(cmd)
    if _BAD_SHELL.search(text):
        raise ValueError("RUNLESS_V2_COMMAND_REJECTED")
    if len(cmd) >= 3 and cmd[:3] == ("python", "-m", "pytest"):
        return cmd
    if len(cmd) >= 3 and cmd[:2] == ("python", "-m") and (
        cmd[2].startswith(_APPROVED_MODULE_PREFIXES) or cmd[2] == "py_compile"
    ):
        return cmd
    raise ValueError("RUNLESS_V2_COMMAND_REJECTED")


class SandboxEvidence(BaseModel):
    name: str
    ok: bool
    command: list[str] | None = None
    stdout_digest: str | None = None
    stderr_digest: str | None = None
    failure_class: FailureClass = FailureClass.NONE
    detail: str = ""


class SandboxProofResult(BaseModel):
    ok: bool
    candidate_sha: str
    task_id: str
    plan: dict[str, Any]
    evidence: list[SandboxEvidence] = Field(default_factory=list)


class SandboxBackend(Protocol):
    async def create(self, **kwargs: Any) -> str: ...
    async def run(
        self,
        session_id: str,
        command: str,
        args: tuple[str, ...] | list[str] = (),
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> dict[str, Any]: ...
    async def stop(self, session_id: str) -> None: ...


@dataclass
class VercelSandboxBackend:
    repository_url: str = _REPOSITORY_URL

    def __post_init__(self) -> None:
        self._boxes: dict[str, Any] = {}

    async def create(
        self,
        *,
        candidate_sha: str,
        github_token: str,
        runtime: str,
        persistent: bool,
        timeout_ms: int,
    ) -> str:
        if runtime != "python3.13":
            raise SandboxExecutionError("RUNLESS_V2_SANDBOX_RUNTIME_UNSUPPORTED")
        try:
            from vercel.sandbox import AsyncSandbox, GitSource
        except Exception as exc:
            raise SandboxExecutionError("RUNLESS_V2_VERCEL_SDK_UNAVAILABLE") from exc
        box = await AsyncSandbox.create(
            runtime="python3.13",
            source=GitSource(
                url=self.repository_url,
                revision=candidate_sha,
                depth=1,
                username="x-access-token",
                password=github_token,
            ),
            timeout=timeout_ms,
        )
        session_id = str(getattr(box, "sandbox_id", None) or id(box))
        self._boxes[session_id] = box
        try:
            version = await asyncio.wait_for(
                box.run_command("python", ["--version"]), timeout=30
            )
            version_text = f"{await version.stdout()}{await version.stderr()}"
            if not version_text.strip().startswith("Python 3.13"):
                raise SandboxExecutionError("RUNLESS_V2_SANDBOX_RUNTIME_MISMATCH")
            bootstrap = await asyncio.wait_for(
                box.run_command(
                    "python",
                    ["-m", "pip", "install", "--disable-pip-version-check", "--quiet", *_MIN_BOOTSTRAP_PACKAGES],
                ),
                timeout=min(300, timeout_ms / 1000),
            )
            if int(getattr(bootstrap, "exit_code", 1)) != 0:
                raise SandboxExecutionError("RUNLESS_V2_SANDBOX_BOOTSTRAP_FAILED")
        except Exception:
            await self.stop(session_id)
            raise
        return session_id

    async def run(
        self,
        session_id: str,
        command: str,
        args: tuple[str, ...] | list[str] = (),
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_ms: int | None = None,
    ) -> dict[str, Any]:
        box = self._boxes.get(session_id)
        if box is None:
            raise SandboxExecutionError("RUNLESS_V2_SANDBOX_SESSION_NOT_FOUND")
        operation = box.run_command(
            command, list(args), cwd=cwd, env=env
        )
        result = (
            await asyncio.wait_for(operation, timeout=timeout_ms / 1000)
            if timeout_ms
            else await operation
        )
        exit_code = int(getattr(result, "exit_code", 1))
        try:
            stdout = str(await result.stdout() or "")
        except Exception:
            stdout = "RUNLESS_V2_STDOUT_UNAVAILABLE"
        try:
            stderr = str(await result.stderr() or "")
        except Exception:
            stderr = "RUNLESS_V2_STDERR_UNAVAILABLE"
        return {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
        }

    async def stop(self, session_id: str) -> None:
        box = self._boxes.pop(session_id, None)
        if box is not None:
            await box.stop()


class SandboxExecutor:
    def __init__(self, *, backend: SandboxBackend | None = None):
        self.backend = backend or VercelSandboxBackend()

    @staticmethod
    def _digest(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    @staticmethod
    def _effective_timeout(requested_seconds: int, plan_seconds: int | None = None) -> int:
        values = [max(1, int(requested_seconds)), _MAX_SANDBOX_SECONDS]
        if plan_seconds is not None:
            values.append(max(1, int(plan_seconds)))
        return min(values)

    async def _load_plan(self, session_id: str, task_id: str, timeout_ms: int) -> dict[str, Any]:
        code = (
            "import json,sys;from pathlib import Path;"
            "p=Path('devsystem/runless_proof_plans')/(sys.argv[1]+'.json');"
            "print(json.dumps(json.loads(p.read_text()),sort_keys=True,separators=(',',':')))"
        )
        result = await self.backend.run(
            session_id, "python", ["-c", code, task_id], cwd=None, timeout_ms=timeout_ms
        )
        if int(result.get("exit_code", 1)) != 0:
            raise SandboxExecutionError("RUNLESS_V2_PLAN_LOAD_FAILED")
        try:
            plan = json.loads(str(result.get("stdout") or ""))
        except Exception as exc:
            raise SandboxExecutionError("RUNLESS_V2_PLAN_DECODE_FAILED") from exc
        if plan.get("task_id") != task_id:
            raise SandboxExecutionError("RUNLESS_V2_PLAN_ID_MISMATCH")
        if not plan.get("freeze_token"):
            raise SandboxExecutionError("RUNLESS_V2_PLAN_REQUIRED_FIELDS")
        return plan

    async def execute(
        self,
        *,
        candidate_sha: str,
        task_id: str,
        github_token: str,
        timeout_seconds: int,
    ) -> SandboxProofResult:
        session_id: str | None = None
        proof_result: SandboxProofResult | None = None
        primary_error: BaseException | None = None
        create_timeout = self._effective_timeout(timeout_seconds)
        try:
            try:
                session_id = await self.backend.create(
                    candidate_sha=candidate_sha,
                    github_token=github_token,
                    runtime="python3.13",
                    persistent=False,
                    timeout_ms=create_timeout * 1000,
                )
            except SandboxExecutionError:
                raise
            except Exception as exc:
                raise SandboxExecutionError("RUNLESS_V2_SANDBOX_CREATE_FAILED") from exc

            head = await self.backend.run(
                session_id, "git", ["rev-parse", "HEAD"], timeout_ms=30_000
            )
            if int(head.get("exit_code", 1)) != 0 or str(head.get("stdout") or "").strip() != candidate_sha:
                raise SandboxExecutionError("RUNLESS_V2_SANDBOX_HEAD_MISMATCH")

            plan = await self._load_plan(session_id, task_id, 30_000)
            plan_timeout = self._effective_timeout(timeout_seconds, int(plan.get("timeout_seconds", timeout_seconds)))
            commands: list[tuple[str, ...]] = []
            for raw in plan.get("commands", []):
                try:
                    commands.append(validate_command(tuple(raw)))
                except ValueError as exc:
                    raise SandboxExecutionError("RUNLESS_V2_COMMAND_REJECTED") from exc

            evidence: list[SandboxEvidence] = []
            for command in commands:
                try:
                    result = await self.backend.run(
                        session_id,
                        command[0],
                        list(command[1:]),
                        timeout_ms=plan_timeout * 1000,
                    )
                    stdout = str(result.get("stdout") or "")
                    stderr = str(result.get("stderr") or "")
                    ok = int(result.get("exit_code", 1)) == 0
                    if ok:
                        failure_class, detail = FailureClass.NONE, ""
                    else:
                        failure_class, detail = _classify_proof_command_failure(stdout, stderr)
                    evidence.append(
                        SandboxEvidence(
                            name=" ".join(command),
                            ok=ok,
                            command=list(command),
                            stdout_digest=self._digest(stdout),
                            stderr_digest=self._digest(stderr),
                            failure_class=failure_class,
                            detail=detail,
                        )
                    )
                    if not ok:
                        break
                except TimeoutError:
                    evidence.append(
                        SandboxEvidence(
                            name=" ".join(command),
                            ok=False,
                            command=list(command),
                            stdout_digest=self._digest(""),
                            stderr_digest=self._digest(""),
                            failure_class=FailureClass.INFRA,
                            detail="RUNLESS_V2_SANDBOX_COMMAND_TIMEOUT",
                        )
                    )
                    break

            proof_result = SandboxProofResult(
                ok=bool(evidence) and all(item.ok for item in evidence),
                candidate_sha=candidate_sha,
                task_id=task_id,
                plan=plan,
                evidence=evidence,
            )
            return proof_result
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            if session_id is not None:
                try:
                    await self.backend.stop(session_id)
                except Exception:
                    if primary_error is None and proof_result is None:
                        raise
