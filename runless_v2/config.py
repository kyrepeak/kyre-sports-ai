from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str
    github_app_id: str
    github_app_installation_id: str
    github_app_private_key: str
    proof_auth_token: str
    repository: str = "kyrepeak/kyre-sports-ai"
    receipt_ref: str = "runless-proof-receipts"
    receipt_path: str = "devsystem/runless_proof_receipts"
    gate_name: str = "runless-final-gate"
    authority_enabled: bool = False
    lease_ttl_seconds: int = 900

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        e = os.environ if env is None else env
        values = {
            "SUPABASE_URL": e.get("SUPABASE_URL", "").strip(),
            "SUPABASE_SERVICE_ROLE_KEY": e.get("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
            "GITHUB_APP_ID": e.get("GITHUB_APP_ID", "").strip(),
            "GITHUB_APP_INSTALLATION_ID": e.get("GITHUB_APP_INSTALLATION_ID", "").strip(),
            "GITHUB_APP_PRIVATE_KEY": e.get("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n").strip(),
            "RUNLESS_PROOF_AUTH_TOKEN": e.get("RUNLESS_PROOF_AUTH_TOKEN", "").strip(),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise RuntimeError("RUNLESS_V2_CONFIG_REQUIRED:" + ",".join(missing))
        if values["GITHUB_APP_ID"] != "5204253":
            raise RuntimeError("RUNLESS_V2_GITHUB_APP_ID_MISMATCH")
        return cls(
            supabase_url=values["SUPABASE_URL"].rstrip("/"),
            supabase_service_role_key=values["SUPABASE_SERVICE_ROLE_KEY"],
            github_app_id=values["GITHUB_APP_ID"],
            github_app_installation_id=values["GITHUB_APP_INSTALLATION_ID"],
            github_app_private_key=values["GITHUB_APP_PRIVATE_KEY"],
            proof_auth_token=values["RUNLESS_PROOF_AUTH_TOKEN"],
            repository=e.get("GITHUB_REPOSITORY", "kyrepeak/kyre-sports-ai").strip() or "kyrepeak/kyre-sports-ai",
            receipt_ref=e.get("RPP_RECEIPT_REF", "runless-proof-receipts").strip() or "runless-proof-receipts",
            receipt_path=e.get("RPP_RECEIPT_PATH", "devsystem/runless_proof_receipts").strip() or "devsystem/runless_proof_receipts",
            gate_name=e.get("RPP_GATE_NAME", "runless-final-gate").strip() or "runless-final-gate",
            authority_enabled=e.get("RUNLESS_AUTHORITY_ENABLED", "").strip() == "1",
            lease_ttl_seconds=int(e.get("RUNLESS_V2_LEASE_TTL_SECONDS", "900")),
        )


def _guardian_shared_runtime_freeze_closeout_maybe_auto_prove() -> None:
    """Publish Guardian closeout proof only from its exact Vercel preview branch."""
    import asyncio

    if os.environ.get("VERCEL_ENV", "").strip() != "preview":
        return
    branch = os.environ.get("VERCEL_GIT_COMMIT_REF", "").strip()
    preview_sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "").strip().lower()
    authorized_branch = "guardian-shared-runtime-lifecycle-freeze-closeout-v1"
    if branch != authorized_branch or len(preview_sha) != 40:
        return
    try:
        from .github_authority import GithubAuthority
        from .guardian_shared_runtime_freeze_closeout_proof_v1 import (
            BRANCH,
            prove_guardian_shared_runtime_freeze_closeout,
        )
        from .sandbox_executor import SandboxExecutor

        if BRANCH != authorized_branch:
            raise RuntimeError("GUARDIAN_SHARED_RUNTIME_FREEZE_CLOSEOUT_BRANCH_CONTRACT_DRIFT")
        settings = Settings.from_env()
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


_guardian_shared_runtime_freeze_closeout_maybe_auto_prove()
