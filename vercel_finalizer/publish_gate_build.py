from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from devsystem.runless_proof_plan_v1 import load_plan

GATE_NAME = "runless-final-gate"
APP_ID_EXPECTED = "5204253"
_TASK_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_IDENTITY_KEYS = ("FINALIZER_TASK_ID", "FINALIZER_WORKSTREAM", "FINALIZER_FENCING_GENERATION")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name}_REQUIRED")
    return value


def _target_task_id() -> str:
    task_id = _required("FINALIZER_TASK_ID")
    if not _TASK_ID.fullmatch(task_id):
        raise RuntimeError("FINALIZER_TASK_ID_INVALID")
    return task_id


def _target_workstream() -> str:
    return _required("FINALIZER_WORKSTREAM")


def _fencing_generation() -> int:
    raw = _required("FINALIZER_FENCING_GENERATION")
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("FINALIZER_FENCING_GENERATION_INVALID") from exc
    if value < 0:
        raise RuntimeError("FINALIZER_FENCING_GENERATION_INVALID")
    return value


def _preview_without_identity() -> bool:
    if os.getenv("VERCEL_ENV", "").strip().lower() != "preview":
        return False
    return all(not os.getenv(key, "").strip() for key in _IDENTITY_KEYS)


def _proof_plan_path() -> Path:
    return ROOT / "devsystem" / "runless_proof_plans" / f"{_target_task_id()}.json"


def _require_candidate() -> str:
    sha = os.getenv("VERCEL_GIT_COMMIT_SHA", "").strip().lower()
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha):
        raise RuntimeError("FINALIZER_VERCEL_SHA_REQUIRED")
    return sha


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
    payload = {
        "candidate_sha": candidate_sha,
        "commands": commands,
        "proof_plan_sha256": hashlib.sha256(_proof_plan_path().read_bytes()).hexdigest(),
        "gate": GATE_NAME,
        "github_app_id": APP_ID_EXPECTED,
        "task_id": _target_task_id(),
        "workstream": _target_workstream(),
        "fencing_generation": _fencing_generation(),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def main() -> int:
    """Build-time exact proof only. Gate publication is owned by dynamic /prove authority."""
    if _preview_without_identity():
        print("RUNLESS_EXACT_PROOF_SKIPPED=preview-without-finalizer-identity", flush=True)
        return 0
    candidate_sha = _require_candidate()
    commands = _run_exact_proof()
    digest = _proof_digest(candidate_sha, commands)
    print(f"RUNLESS_EXACT_PROOF_CANDIDATE={candidate_sha}", flush=True)
    print(f"RUNLESS_EXACT_PROOF_DIGEST={digest}", flush=True)
    print(f"RUNLESS_EXACT_PROOF_WORKSTREAM={_target_workstream()}", flush=True)
    print(f"RUNLESS_EXACT_PROOF_FENCING_GENERATION={_fencing_generation()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
