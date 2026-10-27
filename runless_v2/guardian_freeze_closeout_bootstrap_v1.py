"""Deferred KYRE GUARDIAN proof bootstrap for exact Runless preview branches."""
from __future__ import annotations

import asyncio
import os
from typing import Any

FREEZE_CLOSEOUT_BRANCH = "guardian-shared-runtime-lifecycle-freeze-closeout-v1"
FREEZE_IDEMPOTENCY_BRANCH = "guardian-monster-freeze-idempotency-v1"
STREAM_HANDOFF_BRANCH = "guardian-runless-stream-handoff-v1"
PYTEST_ENTRYPOINT_BRANCH = "guardian-pytest-entrypoint-contract-v1"
INFRASTRUCTURE_AUTOMATION_CLEANUP_BRANCH = "guardian-infrastructure-automation-cleanup-v1"
SECURITY_CONFIGURATION_HARDENING_BRANCH = "guardian-security-configuration-hardening-v1"
SOURCE_PARITY_BRANCH = "guardian-source-parity-archive-v1"


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


def _prove_stream_handoff(settings: Any, preview_sha: str) -> None:
    from .github_authority import GithubAuthority
    from .guardian_runless_stream_handoff_proof_v1 import (
        BRANCH,
        prove_guardian_runless_stream_handoff,
    )
    from .sandbox_executor import SandboxExecutor

    if BRANCH != STREAM_HANDOFF_BRANCH:
        raise RuntimeError("GUARDIAN_RUNLESS_STREAM_HANDOFF_BRANCH_CONTRACT_DRIFT")
    if not settings.authority_enabled:
        raise RuntimeError("GUARDIAN_RUNLESS_STREAM_HANDOFF_AUTHORITY_DISABLED")
    result = asyncio.run(
        prove_guardian_runless_stream_handoff(
            github=GithubAuthority(settings),
            sandbox=SandboxExecutor(),
            expected_preview_sha=preview_sha,
        )
    )
    print(
        "GUARDIAN_RUNLESS_STREAM_HANDOFF_AUTO_PROOF_GREEN:"
        + str(result.get("receipt_digest") or "")
    )


def _prove_pytest_entrypoint(settings: Any, preview_sha: str) -> None:
    from .github_authority import GithubAuthority
    from .guardian_pytest_entrypoint_contract_proof_v1 import (
        BRANCH,
        prove_guardian_pytest_entrypoint_contract,
    )
    from .sandbox_executor import SandboxExecutor

    if BRANCH != PYTEST_ENTRYPOINT_BRANCH:
        raise RuntimeError("GUARDIAN_PYTEST_ENTRYPOINT_BRANCH_CONTRACT_DRIFT")
    if not settings.authority_enabled:
        raise RuntimeError("GUARDIAN_PYTEST_ENTRYPOINT_AUTHORITY_DISABLED")
    result = asyncio.run(
        prove_guardian_pytest_entrypoint_contract(
            github=GithubAuthority(settings),
            sandbox=SandboxExecutor(),
            expected_preview_sha=preview_sha,
        )
    )
    print(
        "GUARDIAN_PYTEST_ENTRYPOINT_AUTO_PROOF_GREEN:"
        + str(result.get("receipt_digest") or "")
    )


def _prove_infrastructure_automation_cleanup(settings: Any, preview_sha: str) -> None:
    from .github_authority import GithubAuthority
    from .guardian_infrastructure_automation_cleanup_proof_v1 import (
        BRANCH,
        prove_guardian_infrastructure_automation_cleanup,
    )
    from .sandbox_executor import SandboxExecutor

    if BRANCH != INFRASTRUCTURE_AUTOMATION_CLEANUP_BRANCH:
        raise RuntimeError("GUARDIAN_INFRASTRUCTURE_AUTOMATION_CLEANUP_BRANCH_CONTRACT_DRIFT")
    if not settings.authority_enabled:
        raise RuntimeError("GUARDIAN_INFRASTRUCTURE_AUTOMATION_CLEANUP_AUTHORITY_DISABLED")
    result = asyncio.run(
        prove_guardian_infrastructure_automation_cleanup(
            github=GithubAuthority(settings),
            sandbox=SandboxExecutor(),
            expected_preview_sha=preview_sha,
        )
    )
    print(
        "GUARDIAN_INFRASTRUCTURE_AUTOMATION_CLEANUP_AUTO_PROOF_GREEN:"
        + str(result.get("receipt_digest") or "")
    )


def _prove_security_configuration_hardening(settings: Any, preview_sha: str) -> None:
    from .github_authority import GithubAuthority
    from .guardian_security_configuration_hardening_proof_v1 import (
        BRANCH,
        prove_guardian_security_configuration_hardening,
    )
    from .sandbox_executor import SandboxExecutor

    if BRANCH != SECURITY_CONFIGURATION_HARDENING_BRANCH:
        raise RuntimeError("GUARDIAN_SECURITY_CONFIGURATION_HARDENING_BRANCH_CONTRACT_DRIFT")
    if not settings.authority_enabled:
        raise RuntimeError("GUARDIAN_SECURITY_CONFIGURATION_HARDENING_AUTHORITY_DISABLED")
    result = asyncio.run(
        prove_guardian_security_configuration_hardening(
            github=GithubAuthority(settings),
            sandbox=SandboxExecutor(),
            expected_preview_sha=preview_sha,
        )
    )
    print(
        "GUARDIAN_SECURITY_CONFIGURATION_HARDENING_AUTO_PROOF_GREEN:"
        + str(result.get("receipt_digest") or "")
    )


def _prove_source_parity(settings: Any, preview_sha: str) -> None:
    from .github_authority import GithubAuthority
    from .guardian_source_of_truth_configuration_parity_proof_v1 import (
        BRANCH,
        prove_guardian_source_of_truth_configuration_parity,
    )
    from .sandbox_executor import SandboxExecutor

    if BRANCH != SOURCE_PARITY_BRANCH:
        raise RuntimeError("GUARDIAN_SOURCE_PARITY_BRANCH_CONTRACT_DRIFT")
    if not settings.authority_enabled:
        raise RuntimeError("GUARDIAN_SOURCE_PARITY_AUTHORITY_DISABLED")
    result = asyncio.run(
        prove_guardian_source_of_truth_configuration_parity(
            github=GithubAuthority(settings),
            sandbox=SandboxExecutor(),
            expected_preview_sha=preview_sha,
        )
    )
    print(
        "GUARDIAN_SOURCE_PARITY_AUTO_PROOF_GREEN:"
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
    elif branch == STREAM_HANDOFF_BRANCH:
        runner = _prove_stream_handoff
        blocked_prefix = "GUARDIAN_RUNLESS_STREAM_HANDOFF_AUTO_PROOF_BLOCKED:"
    elif branch == PYTEST_ENTRYPOINT_BRANCH:
        runner = _prove_pytest_entrypoint
        blocked_prefix = "GUARDIAN_PYTEST_ENTRYPOINT_AUTO_PROOF_BLOCKED:"
    elif branch == INFRASTRUCTURE_AUTOMATION_CLEANUP_BRANCH:
        runner = _prove_infrastructure_automation_cleanup
        blocked_prefix = "GUARDIAN_INFRASTRUCTURE_AUTOMATION_CLEANUP_AUTO_PROOF_BLOCKED:"
    elif branch == SECURITY_CONFIGURATION_HARDENING_BRANCH:
        runner = _prove_security_configuration_hardening
        blocked_prefix = "GUARDIAN_SECURITY_CONFIGURATION_HARDENING_AUTO_PROOF_BLOCKED:"
    elif branch == SOURCE_PARITY_BRANCH:
        runner = _prove_source_parity
        blocked_prefix = "GUARDIAN_SOURCE_PARITY_AUTO_PROOF_BLOCKED:"
    else:
        return
    try:
        runner(settings, preview_sha)
    except Exception as exc:
        detail = str(exc)
        safe_detail = detail if detail.startswith("GUARDIAN_") else type(exc).__name__
        print(blocked_prefix + type(exc).__name__ + ":" + safe_detail[:200])
