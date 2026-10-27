"""Deferred KYRE GUARDIAN proof bootstrap for exact Runless preview branches."""
from __future__ import annotations

import asyncio
import os
from typing import Any

FREEZE_CLOSEOUT_BRANCH = "guardian-shared-runtime-lifecycle-freeze-closeout-v1"
FREEZE_IDEMPOTENCY_BRANCH = "guardian-monster-freeze-idempotency-v1"


def _prove_freeze_closeout(settings: Any, preview_sha: str) -> None:
    from .github_authority import GithubAuthority
    from .guardian_shared_runtime_freeze_closeout_proof_v1 import (
        BRANCH,
        prove_guardian_shared_runtime_freeze_closeout,
    )
    from .sandbox_executor import SandboxExecutor

    if BRANCH != FREEZE_CLOSEOUT_BRANCH:
        raise RuntimeError("GUARDIAN_SHARED_RUNTIME_FREEZE_CLOSEOUT_BRANCH_CONTRACT_DRIFT")
    if not settings.authority_enabled:
        raise RuntimeError("GUARDIAN_SHARED_RUNTIME_FREEZE_CLOSEOUT_AUTHORITY_DISABLED")
    result = asyncio.run(
        prove_guardian_shared_runtime_freeze_closeout(
            github=GithubAuthority(settings),
            sandbox=SandboxExecutor(),
            expected_preview_sha=preview_sha,
        )
    )
    print(
        "GUARDIAN_SHARED_RUNTIME_FREEZE_CLOSEOUT_AUTO_PROOF_GREEN:"
        + str(result.get("receipt_digest") or "")
    )


def _prove_freeze_idempotency(settings: Any, preview_sha: str) -> None:
    from .github_authority import GithubAuthority
    from .guardian_monster_freeze_idempotency_proof_v1 import (
        BRANCH,
        prove_guardian_monster_freeze_idempotency,
    )
    from .sandbox_executor import SandboxExecutor

    if BRANCH != FREEZE_IDEMPOTENCY_BRANCH:
        raise RuntimeError("GUARDIAN_MONSTER_FREEZE_IDEMPOTENCY_BRANCH_CONTRACT_DRIFT")
    if not settings.authority_enabled:
        raise RuntimeError("GUARDIAN_MONSTER_FREEZE_IDEMPOTENCY_AUTHORITY_DISABLED")
    result = asyncio.run(
        prove_guardian_monster_freeze_idempotency(
            github=GithubAuthority(settings),
            sandbox=SandboxExecutor(),
            expected_preview_sha=preview_sha,
        )
    )
    print(
        "GUARDIAN_MONSTER_FREEZE_IDEMPOTENCY_AUTO_PROOF_GREEN:"
        + str(result.get("receipt_digest") or "")
    )


def maybe_auto_prove(settings: Any) -> None:
    """Publish Guardian proof only from an explicitly authorized preview branch."""
    if os.environ.get("VERCEL_ENV", "").strip() != "preview":
        return
    branch = os.environ.get("VERCEL_GIT_COMMIT_REF", "").strip()
    preview_sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "").strip().lower()
    if len(preview_sha) != 40:
        return
    if branch == FREEZE_CLOSEOUT_BRANCH:
        runner = _prove_freeze_closeout
        blocked_prefix = "GUARDIAN_SHARED_RUNTIME_FREEZE_CLOSEOUT_AUTO_PROOF_BLOCKED:"
    elif branch == FREEZE_IDEMPOTENCY_BRANCH:
        runner = _prove_freeze_idempotency
        blocked_prefix = "GUARDIAN_MONSTER_FREEZE_IDEMPOTENCY_AUTO_PROOF_BLOCKED:"
    else:
        return
    try:
        runner(settings, preview_sha)
    except Exception as exc:
        detail = str(exc)
        safe_detail = detail if detail.startswith("GUARDIAN_") else type(exc).__name__
        print(blocked_prefix + type(exc).__name__ + ":" + safe_detail[:200])
