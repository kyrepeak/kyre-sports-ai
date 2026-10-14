from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import httpx

from app import (
    ALLOWED_BRANCH,
    APP_ID_EXPECTED,
    GATE_NAME,
    REPOSITORY,
    Settings,
    _existing_success,
    _headers,
    _installation_token,
    _publish_success,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from devsystem.runless_proof_plan_v1 import load_plan

DEFAULT_PR_NUMBER = 1526
DEFAULT_TASK_ID = "universal-sports-source-finalization-v1-step1"
_TASK_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

PHASE_CANDIDATE = 11
PHASE_PROOF = 12
PHASE_CONFIG = 13
PHASE_INSTALLATION_TOKEN = 14
PHASE_PR_HEAD = 15
PHASE_EXISTING_CHECK = 16
PHASE_PUBLISH_CHECK = 17
PHASE_READBACK = 18


def _target_branch() -> str:
    branch = os.getenv("FINALIZER_ALLOWED_BRANCH", ALLOWED_BRANCH).strip()
    if not branch:
        raise RuntimeError("FINALIZER_ALLOWED_BRANCH_REQUIRED")
    return branch


def _target_pr_number() -> int:
    raw = os.getenv("FINALIZER_PR_NUMBER", str(DEFAULT_PR_NUMBER)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("FINALIZER_PR_NUMBER_INVALID") from exc
    if value <= 0:
        raise RuntimeError("FINALIZER_PR_NUMBER_INVALID")
    return value


def _target_task_id() -> str:
    task_id = os.getenv("FINALIZER_TASK_ID", DEFAULT_TASK_ID).strip()
    if not _TASK_ID.fullmatch(task_id):
        raise RuntimeError("FINALIZER_TASK_ID_INVALID")
    return task_id


def _proof_plan_path() -> Path:
    return ROOT / "devsystem" / "runless_proof_plans" / f"{_target_task_id()}.json"


def _require_candidate() -> tuple[str, str]:
    sha = os.getenv("VERCEL_GIT_COMMIT_SHA", "").strip().lower()
    ref = os.getenv("VERCEL_GIT_COMMIT_REF", "").strip()
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha):
        raise RuntimeError("FINALIZER_VERCEL_SHA_REQUIRED")
    allowed_branch = _target_branch()
    if ref and ref != allowed_branch:
        raise RuntimeError("FINALIZER_VERCEL_REF_MISMATCH")
    return sha, ref


def _run_exact_proof() -> list[list[str]]:
    plan = load_plan(_target_task_id(), ROOT)
    commands: list[list[str]] = []
    for raw in plan.commands:
        command = list(raw)
        if command and command[0] == "python":
            command[0] = sys.executable
        subprocess.run(command, cwd=ROOT, check=True)
        commands.append(command)
    return commands


def _proof_digest(candidate_sha: str, commands: list[list[str]]) -> str:
    proof_plan_bytes = _proof_plan_path().read_bytes()
    payload = {
        "candidate_sha": candidate_sha,
        "commands": commands,
        "proof_plan_sha256": hashlib.sha256(proof_plan_bytes).hexdigest(),
        "gate": GATE_NAME,
        "github_app_id": APP_ID_EXPECTED,
        "pr_number": _target_pr_number(),
        "target_branch": _target_branch(),
        "task_id": _target_task_id(),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _verify_pr_head(client: httpx.Client, token: str, candidate_sha: str) -> None:
    response = client.get(
        f"https://api.github.com/repos/{REPOSITORY}/pulls/{_target_pr_number()}",
        headers=_headers(token),
    )
    response.raise_for_status()
    payload = response.json()
    head_sha = str(payload["head"]["sha"]).lower()
    head_ref = str(payload["head"]["ref"])
    if head_ref != _target_branch() or head_sha != candidate_sha:
        raise RuntimeError("FINALIZER_PR_HEAD_MISMATCH")


def _phase_failure(code: int, phase: str, exc: BaseException) -> int:
    print(f"FINALIZER_PHASE_FAILED={phase}", flush=True)
    print(f"FINALIZER_PHASE_EXCEPTION={type(exc).__name__}", flush=True)
    return code


def main() -> int:
    try:
        candidate_sha, _ = _require_candidate()
    except Exception as exc:
        return _phase_failure(PHASE_CANDIDATE, "CANDIDATE_IDENTITY", exc)

    try:
        commands = _run_exact_proof()
        digest = _proof_digest(candidate_sha, commands)
    except Exception as exc:
        return _phase_failure(PHASE_PROOF, "EXACT_PROOF", exc)

    try:
        settings = Settings.from_env()
    except Exception as exc:
        return _phase_failure(PHASE_CONFIG, "GITHUB_APP_CONFIG", exc)

    with httpx.Client(timeout=15) as client:
        try:
            token = _installation_token(settings, client)
        except Exception as exc:
            return _phase_failure(PHASE_INSTALLATION_TOKEN, "INSTALLATION_TOKEN", exc)

        try:
            _verify_pr_head(client, token, candidate_sha)
        except Exception as exc:
            return _phase_failure(PHASE_PR_HEAD, "PR_HEAD", exc)

        try:
            existing = _existing_success(client, token, candidate_sha)
        except Exception as exc:
            return _phase_failure(PHASE_EXISTING_CHECK, "EXISTING_CHECK", exc)

        if existing:
            print(f"RUNLESS_FINAL_GATE_REUSED={candidate_sha}", flush=True)
            print(f"RUNLESS_FINAL_GATE_PROOF_DIGEST={digest}", flush=True)
            return 0

        try:
            _publish_success(client, token, candidate_sha, digest)
        except Exception as exc:
            return _phase_failure(PHASE_PUBLISH_CHECK, "PUBLISH_CHECK", exc)

        try:
            if not _existing_success(client, token, candidate_sha):
                raise RuntimeError("FINALIZER_CHECK_READBACK_FAILED")
        except Exception as exc:
            return _phase_failure(PHASE_READBACK, "CHECK_READBACK", exc)

    print(f"RUNLESS_FINAL_GATE_SUCCESS={candidate_sha}", flush=True)
    print(f"RUNLESS_FINAL_GATE_PROOF_DIGEST={digest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
