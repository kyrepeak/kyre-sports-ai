"""Runless composition for WNBA PRA Page 1 final polish V1.

The frozen snapshot implementation remains unchanged on disk. This compatibility
layer installs a successor artifact builder and a narrow identity allowlist at
Runless package bootstrap, preserving the same one-read public Kyre API route.
"""
from __future__ import annotations

import json
import os
from typing import Any, Mapping

from . import wnba_pra_page_snapshot_v1 as snapshot

_BASE_SAFE_MODEL_FIELDS = snapshot._safe_model_fields
_INSTALLED = False


def _positive_int(value: Any) -> int | None:
    try:
        result = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result > 0 else None


def _safe_model_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    out = _BASE_SAFE_MODEL_FIELDS(row)
    player_id = _positive_int(row.get("player_id"))
    team_id = _positive_int(row.get("team_id"))
    if player_id:
        out["player_id"] = player_id
        out["headshot_url"] = f"https://cdn.wnba.com/headshots/wnba/latest/1040x760/{player_id}.png"
    if team_id:
        out["team_id"] = team_id
        out["team_logo_url"] = f"https://cdn.nba.com/logos/wnba/{team_id}/global/L/logo.svg"
    return out


async def _artifact_from_exact_sha_sandbox(date: str, season: int) -> dict[str, Any]:
    from .config import Settings
    from .github_authority import GithubAuthority
    from .sandbox_executor import VercelSandboxBackend

    settings = Settings.from_env()
    github = GithubAuthority(settings)
    candidate_sha = str(os.environ.get("VERCEL_GIT_COMMIT_SHA") or github.main_sha()).strip().lower()
    if len(candidate_sha) != 40 or any(ch not in "0123456789abcdef" for ch in candidate_sha):
        raise RuntimeError("WNBA_PRA_REFRESH_SHA_INVALID")
    backend = VercelSandboxBackend()
    session_id = await backend.create(
        candidate_sha=candidate_sha,
        github_token=github.installation_token(),
        runtime="python3.13",
        persistent=False,
        timeout_ms=240000,
    )
    code = (
        "import json,sys;"
        "from wnba_pra_page_model_artifact_final_polish_v1 import build_model_artifact,_hash_payload,validate_model_artifact;"
        "a=build_model_artifact(sys.argv[1],int(sys.argv[2]));"
        "s={k:a[k] for k in ('schema_version','date','season','generated_at','model_version','source_status','blocked_fallback_calls','rows','line_bindings','final_card')};"
        "s['content_hash']=_hash_payload(s);validate_model_artifact(s);"
        "print(json.dumps(s,sort_keys=True,separators=(',',':')))"
    )
    try:
        result = await backend.run(
            session_id,
            "python",
            ["-c", code, str(date), str(int(season))],
            timeout_ms=210000,
        )
        if int(result.get("exit_code", 1)) != 0:
            raise RuntimeError("WNBA_PRA_REFRESH_SANDBOX_FAILED")
        lines = [line for line in str(result.get("stdout") or "").splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("WNBA_PRA_REFRESH_SANDBOX_EMPTY")
        return snapshot.validate_artifact_light(json.loads(lines[-1]))
    finally:
        await backend.stop(session_id)


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    snapshot._safe_model_fields = _safe_model_fields
    snapshot._artifact_from_exact_sha_sandbox = _artifact_from_exact_sha_sandbox
    _INSTALLED = True


install()

__all__ = ["install", "_safe_model_fields", "_artifact_from_exact_sha_sandbox"]
