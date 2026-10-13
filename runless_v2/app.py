from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

# Vercel imports this file as standalone /var/task/app.py when runless_v2 is
# configured as the project root. Recreate the package context so the existing
# relative imports keep working without rewriting the Runless V2 modules.
if not __package__:
    _package_dir = Path(__file__).resolve().parent
    _package_spec = importlib.util.spec_from_file_location(
        "runless_v2",
        _package_dir / "__init__.py",
        submodule_search_locations=[str(_package_dir)],
    )
    if _package_spec is None or _package_spec.loader is None:
        raise ImportError("RUNLESS_V2_PACKAGE_BOOTSTRAP_FAILED")
    _package_module = importlib.util.module_from_spec(_package_spec)
    sys.modules["runless_v2"] = _package_module
    _package_spec.loader.exec_module(_package_module)
    __package__ = "runless_v2"

from . import VERSION
from .auth import require_bearer
from .config import Settings
from .finalization_readback import validate_finalization_closeout
from .github_authority import GithubAuthority, GithubAuthorityError
from .models import ProofRequest, ProofResult
from .proof_service import ProofServiceError, execute_proof_request
from .sandbox_executor import SandboxExecutor
from .state_store import DurableStateStore, RunlessV2StateError

_LEDGER_BRANCH = "monster-finalization-ledger-v2"
_MANIFEST_PATH = "devsystem/finalization_ledger_v2/manifest.json"


class CloseoutRequest(BaseModel):
    proof_id: str
    workstream: str
    candidate_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    merged_main_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    freeze_token: str
    proof_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def _supabase_health(store: Any) -> bool:
    health = getattr(store, "health", None)
    if callable(health):
        try:
            return bool(health())
        except Exception:
            return False
    try:
        response = store.client.get(
            store._url("/rest/v1/proof_runs"),
            headers=store._headers,
            params={"select": "proof_id", "limit": "1"},
        )
        return response.status_code < 500
    except Exception:
        return False


def _read_finalization_evidence(github: Any, freeze_token: str) -> dict[str, Any]:
    helper = getattr(github, "read_finalization_evidence", None)
    if callable(helper):
        return helper(freeze_token)

    record_path = f"devsystem/finalization_ledger_v2/records/{freeze_token}.json"
    record = github._content_json(record_path, _LEDGER_BRANCH)
    manifest = github._content_json(_MANIFEST_PATH, _LEDGER_BRANCH)
    history = github._request(
        "GET",
        f"/commits?sha={quote(_LEDGER_BRANCH, safe='')}&path={quote(_MANIFEST_PATH, safe='/')}&per_page=2",
    )
    previous_manifest = None
    if int(manifest.get("revision", 0)) > 1:
        if not isinstance(history, list) or len(history) < 2:
            raise GithubAuthorityError("RUNLESS_V2_FINALIZATION_HISTORY_REQUIRED")
        previous_manifest = github._content_json(_MANIFEST_PATH, str(history[1]["sha"]))
    return {
        "record": record,
        "manifest": manifest,
        "previous_manifest": previous_manifest,
    }


def create_app(
    *,
    settings: Settings | None = None,
    state_store: Any | None = None,
    github: Any | None = None,
    sandbox_executor: Any | None = None,
    proof_executor: Callable[..., Awaitable[ProofResult]] | None = None,
) -> FastAPI:
    cfg = settings or Settings.from_env()
    store = state_store or DurableStateStore(cfg)
    gh = github or GithubAuthority(cfg)
    sandbox = sandbox_executor or SandboxExecutor()
    execute = proof_executor or execute_proof_request

    app = FastAPI(title="Runless V2 Proof Authority", version="2")
    app.state.settings = cfg
    app.state.state_store = store
    app.state.github = gh
    app.state.sandbox = sandbox

    def authenticated(authorization: str | None = Header(default=None)) -> None:
        require_bearer(authorization, cfg.proof_auth_token)

    @app.get("/health")
    def health() -> dict[str, Any]:
        supabase_ok = _supabase_health(store)
        return {
            "status": "healthy" if supabase_ok else "degraded",
            "service": "runless-v2",
            "version": VERSION,
            "supabase": "healthy" if supabase_ok else "unavailable",
            "github_app_configured": bool(
                cfg.github_app_id == "5204253"
                and cfg.github_app_installation_id
                and cfg.github_app_private_key
            ),
            "proof_authority_enabled": cfg.authority_enabled,
            "render_dependency": False,
            "github_actions_fallback": 0,
        }

    @app.post("/prove", dependencies=[Depends(authenticated)])
    async def prove(req: ProofRequest) -> dict[str, Any]:
        if not cfg.authority_enabled:
            raise HTTPException(status_code=503, detail="RUNLESS_V2_AUTHORITY_DISABLED")
        try:
            result = await execute(req, state_store=store, github=gh, sandbox=sandbox)
            return result.model_dump(mode="json")
        except (RunlessV2StateError, GithubAuthorityError, ProofServiceError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"RUNLESS_V2_PROOF_UNAVAILABLE:{type(exc).__name__}",
            ) from exc

    @app.get("/status/{proof_id}", dependencies=[Depends(authenticated)])
    def proof_status(proof_id: str) -> dict[str, Any]:
        try:
            return store.status(proof_id).model_dump(mode="json")
        except (KeyError, IndexError):
            raise HTTPException(status_code=404, detail="RUNLESS_V2_PROOF_NOT_FOUND")
        except RunlessV2StateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/receipts/{proof_id}", dependencies=[Depends(authenticated)])
    def receipt_status(proof_id: str) -> dict[str, Any]:
        try:
            return store.receipt_mirror(proof_id)
        except (KeyError, IndexError):
            raise HTTPException(status_code=404, detail="RUNLESS_V2_RECEIPT_NOT_FOUND")
        except RunlessV2StateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/closeout", dependencies=[Depends(authenticated)])
    def closeout(req: CloseoutRequest) -> dict[str, Any]:
        if not cfg.authority_enabled:
            raise HTTPException(status_code=503, detail="RUNLESS_V2_AUTHORITY_DISABLED")
        try:
            evidence = _read_finalization_evidence(gh, req.freeze_token)
            verified = validate_finalization_closeout(
                evidence["record"],
                evidence["manifest"],
                expected_workstream=req.workstream,
                expected_freeze_token=req.freeze_token,
                expected_candidate_sha=req.candidate_sha,
                expected_proof_digest=req.proof_digest,
                expected_merged_main_sha=req.merged_main_sha,
                previous_manifest=evidence.get("previous_manifest"),
            )
            durable = store.closeout_green_frozen(
                req.proof_id,
                candidate_sha=req.candidate_sha,
                merged_main_sha=req.merged_main_sha,
                freeze_token=req.freeze_token,
                proof_digest=req.proof_digest,
                manifest_state_hash=verified["manifest_state_hash"],
            )
            return durable.model_dump(mode="json")
        except (RunlessV2StateError, GithubAuthorityError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"RUNLESS_V2_CLOSEOUT_UNAVAILABLE:{type(exc).__name__}",
            ) from exc

    return app


def _unconfigured_app(error: BaseException) -> FastAPI:
    fallback = FastAPI(title="Runless V2 Proof Authority", version="2")

    @fallback.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "unconfigured",
            "service": "runless-v2",
            "version": VERSION,
            "proof_authority_enabled": False,
            "render_dependency": False,
            "github_actions_fallback": 0,
            "configuration_error": type(error).__name__,
        }

    return fallback


# Vercel's FastAPI preset requires a directly detectable top-level instance.
# The real configured app replaces this sentinel immediately at import time.
app = FastAPI(title="Runless V2 Proof Authority", version="2")

try:
    app = create_app()
except Exception as _bootstrap_error:
    app = _unconfigured_app(_bootstrap_error)
