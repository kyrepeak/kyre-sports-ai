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
        settings = cls(
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
        # Deferred import avoids circular config/github-authority initialization.
        from .guardian_freeze_closeout_bootstrap_v1 import maybe_auto_prove

        maybe_auto_prove(settings)
        return settings
