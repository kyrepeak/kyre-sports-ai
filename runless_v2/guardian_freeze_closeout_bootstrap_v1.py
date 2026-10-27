"""Deferred KYRE GUARDIAN freeze-closeout bootstrap for Runless previews."""
from __future__ import annotations

import asyncio
import os
from typing import Any

AUTHORIZED_BRANCH = "guardian-shared-runtime-lifecycle-freeze-closeout-v1"


def maybe_auto_prove(settings: Any) -> None:
    """Publish Guardian closeout proof only from its exact Vercel preview head."""
    if os.environ.get("VERCEL_ENV", "").strip() != "preview":
        return
    branch = os.environ.get("VERCEL_GIT_COMMIT_REF", "").strip()
    preview_sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "").strip().lower()
    if branch != AUTHORIZED_BRANCH or len(preview_sha) != 40:
        return
    try:
        from .github_authority import GithubAuthority
        from .guardian_shared_runtime_freeze_closeout_proof_v1 import (
            BRANCH,
            prove_guardian_shared_runtime_freeze_closeout,
        )
        from .sandbox_executor import SandboxExecutor

        if BRANCH != AUTHORIZED_BRANCH:
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
    except Exception as exc:
        detail = str(exc)
        safe_detail = detail if detail.startswith("GUARDIAN_") else type(exc).__name__
        print(
            "GUARDIAN_SHARED_RUNTIME_FREEZE_CLOSEOUT_AUTO_PROOF_BLOCKED:"
            + type(exc).__name__
            + ":"
            + safe_detail[:200]
        )
