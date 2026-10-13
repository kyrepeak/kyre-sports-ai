from __future__ import annotations

import hashlib
import json
import os
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
PROOF_PLAN = ROOT / "devsystem" / "runless_proof_plans" / "universal-sports-source-finalization-v1-step1.json"


def _require_candidate() -> tuple[str, str]:
    sha = os.getenv("VERCEL_GIT_COMMIT_SHA", "").strip().lower()
    ref = os.getenv("VERCEL_GIT_COMMIT_REF", "").strip()
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha):
        raise RuntimeError("FINALIZER_VERCEL_SHA_REQUIRED")
    if ref and ref != ALLOWED_BRANCH:
        raise RuntimeError("FINALIZER_VERCEL_REF_MISMATCH")
    return sha, ref


def _run_exact_proof() -> list[list[str]]:
    commands = [
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_devsystem_universal_sports_source_finalization_step1_v1.py",
        ],
        [
            sys.executable,
            "-m",
            "py_compile",
            "devsystem/universal_sports_source_finalization_step1_contract_v1.py",
            "devsystem/universal_sports_finalization_bootstrap_v1.py",
        ],
        [sys.executable, "-m", "pytest", "-q", "vercel_finalizer/test_app.py"],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    return commands


def _proof_digest(candidate_sha: str, commands: list[list[str]]) -> str:
    proof_plan_bytes = PROOF_PLAN.read_bytes()
    payload = {
        "candidate_sha": candidate_sha,
        "commands": commands,
        "proof_plan_sha256": hashlib.sha256(proof_plan_bytes).hexdigest(),
        "gate": GATE_NAME,
        "github_app_id": APP_ID_EXPECTED,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _verify_pr_head(client: httpx.Client, token: str, candidate_sha: str) -> None:
    response = client.get(
        f"https://api.github.com/repos/{REPOSITORY}/pulls/1526",
        headers=_headers(token),
    )
    response.raise_for_status()
    payload = response.json()
    head_sha = str(payload["head"]["sha"]).lower()
    head_ref = str(payload["head"]["ref"])
    if head_ref != ALLOWED_BRANCH or head_sha != candidate_sha:
        raise RuntimeError("FINALIZER_PR_HEAD_MISMATCH")


def main() -> int:
    candidate_sha, _ = _require_candidate()
    commands = _run_exact_proof()
    digest = _proof_digest(candidate_sha, commands)
    settings = Settings.from_env()

    with httpx.Client(timeout=15) as client:
        token = _installation_token(settings, client)
        _verify_pr_head(client, token, candidate_sha)
        if _existing_success(client, token, candidate_sha):
            print(f"RUNLESS_FINAL_GATE_REUSED={candidate_sha}")
            print(f"RUNLESS_FINAL_GATE_PROOF_DIGEST={digest}")
            return 0

        _publish_success(client, token, candidate_sha, digest)
        if not _existing_success(client, token, candidate_sha):
            raise RuntimeError("FINALIZER_CHECK_READBACK_FAILED")

    print(f"RUNLESS_FINAL_GATE_SUCCESS={candidate_sha}")
    print(f"RUNLESS_FINAL_GATE_PROOF_DIGEST={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
