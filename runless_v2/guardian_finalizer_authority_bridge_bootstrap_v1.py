"""Deferred KYRE GUARDIAN proof bootstrap for Finalizer capability V1."""
from __future__ import annotations

import asyncio
import os
from typing import Any

BRANCH = "guardian-finalizer-authority-bridge-v1"


def maybe_auto_prove(settings: Any) -> None:
    if os.environ.get("VERCEL_ENV", "").strip() != "preview":
        return
    branch = os.environ.get("VERCEL_GIT_COMMIT_REF", "").strip()
    preview_sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "").strip().lower()
    if branch != BRANCH or len(preview_sha) != 40:
        return

    try:
        from .github_authority import GithubAuthority
        from .guardian_finalizer_authority_bridge_proof_v1 import (
            BRANCH as PROOF_BRANCH,
            prove_guardian_finalizer_authority_bridge,
        )
        from .sandbox_executor import SandboxExecutor

        if PROOF_BRANCH != BRANCH:
            raise RuntimeError("GUARDIAN_FINALIZER_AUTHORITY_BRIDGE_BRANCH_CONTRACT_DRIFT")
        if not settings.authority_enabled:
            raise RuntimeError("GUARDIAN_FINALIZER_AUTHORITY_BRIDGE_AUTHORITY_DISABLED")
        result = asyncio.run(
            prove_guardian_finalizer_authority_bridge(
                github=GithubAuthority(settings),
                sandbox=SandboxExecutor(),
                expected_preview_sha=preview_sha,
            )
        )
        print(
            "GUARDIAN_FINALIZER_AUTHORITY_BRIDGE_AUTO_PROOF_GREEN:"
            + str(result.get("receipt_digest") or "")
        )
    except Exception as exc:
        detail = str(exc)
        safe_detail = detail if detail.startswith("GUARDIAN_") else type(exc).__name__
        print(
            "GUARDIAN_FINALIZER_AUTHORITY_BRIDGE_AUTO_PROOF_BLOCKED:"
            + type(exc).__name__
            + ":"
            + safe_detail[:200]
        )
