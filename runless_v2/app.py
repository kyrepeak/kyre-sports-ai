from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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
from .github_authority import (
    REGISTRY_BRANCH,
    REGISTRY_PATH,
    GithubAuthority,
    GithubAuthorityError,
)
from .models import ProofRequest, ProofResult, ProofState
from .nba_pra_market_v1 import router as nba_pra_market_router
from .nba_pra_player_context_v1 import router as nba_pra_player_context_router
from .nba_pra_schedule_v1 import router as nba_pra_schedule_router
from .nba_pra_injury_v1 import router as nba_pra_injury_router
from .nba_pra_matchup_v1 import router as nba_pra_matchup_router
from .wnba_pra_market_v1 import router as wnba_pra_market_router
from .wnba_schedule_v1 import router as wnba_schedule_router
from .proof_service import ProofServiceError, execute_proof_request
from .sandbox_executor import SandboxExecutor
from .state_store import DurableStateStore, RunlessV2StateError

_LEDGER_BRANCH = "monster-finalization-ledger-v2"
_MANIFEST_PATH = "devsystem/finalization_ledger_v2/manifest.json"


class BaseDriftSupersessionRequest(BaseModel):
    repository: str = Field(min_length=1)
    workstream: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    old_proof_id: str = Field(min_length=1)
    old_candidate_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    successor_candidate_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    successor_expected_main_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    pr_number: int = Field(gt=0)
    branch: str = Field(min_length=1)


class CloseoutRequest(BaseModel):
    proof_id: str
    workstream: str
    candidate_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    merged_main_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    freeze_token: str
    proof_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class RegistryThawRequest(BaseModel):
    repository: str = Field(min_length=1)
    workstream: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    candidate_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    thaw_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    from_blob: str = Field(pattern=r"^[0-9a-f]{40}$")
    to_blob: str = Field(pattern=r"^[0-9a-f]{40}$")
    expected_main_sha: str = Field(pattern=r"^[0-9a-f]{40}$")


class RegistryForwardPortRequest(BaseModel):
    repository: str = Field(min_length=1)
    workstream: str = Field(min_length=1)
    candidate_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    merged_main_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    thaw_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    from_blob: str = Field(pattern=r"^[0-9a-f]{40}$")
    to_blob: str = Field(pattern=r"^[0-9a-f]{40}$")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _registry_state_hash(registry: dict[str, Any]) -> str:
    payload = copy.deepcopy(registry)
    payload.pop("state_hash", None)
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _decode_registry_content(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("encoding") != "base64":
        raise GithubAuthorityError("REGISTRY_THAW_CONTENT_READ_FAILED")
    try:
        decoded = base64.b64decode(str(raw["content"])).decode("utf-8")
        value = json.loads(decoded)
    except Exception as exc:
        raise GithubAuthorityError("REGISTRY_THAW_CONTENT_DECODE_FAILED") from exc
    if not isinstance(value, dict):
        raise GithubAuthorityError("REGISTRY_THAW_CONTENT_INVALID")
    return value


def _registry_thaw_result(
    req: RegistryThawRequest,
    registry: dict[str, Any],
    *,
    previous_revision: int,
    previous_state_hash: str,
    registry_commit_sha: str | None,
    reused: bool,
) -> dict[str, Any]:
    return {
        "thaw_id": req.thaw_id,
        "target_head_sha": req.candidate_sha,
        "path": req.path,
        "from_blob": req.from_blob,
        "to_blob": req.to_blob,
        "previous_registry_revision": previous_revision,
        "current_registry_revision": int(registry["revision"]),
        "previous_state_hash": previous_state_hash,
        "current_state_hash": str(registry["state_hash"]),
        "registry_commit_sha": registry_commit_sha,
        "state": "ACTIVE",
        "reused": reused,
        "failure_class": "NONE",
        "detail": "",
    }


def _execute_registry_thaw(
    req: RegistryThawRequest,
    *,
    settings: Settings,
    github: Any,
) -> dict[str, Any]:
    if req.repository != settings.repository:
        raise GithubAuthorityError("REGISTRY_THAW_REPOSITORY_MISMATCH")
    if req.from_blob == req.to_blob:
        raise GithubAuthorityError("REGISTRY_THAW_NOOP_REJECTED")

    current_main = str(github.main_sha())
    if current_main != req.expected_main_sha:
        raise GithubAuthorityError("REGISTRY_THAW_MAIN_IDENTITY_DRIFT")

    main_tree = github.tree_blobs(req.expected_main_sha)
    candidate_tree = github.tree_blobs(req.candidate_sha)
    if str(main_tree.get(req.path) or "").lower() != req.from_blob:
        raise GithubAuthorityError("REGISTRY_THAW_FROM_BLOB_MISMATCH")
    if str(candidate_tree.get(req.path) or "").lower() != req.to_blob:
        raise GithubAuthorityError("REGISTRY_THAW_TO_BLOB_MISMATCH")

    registry_api_path = f"/contents/{quote(REGISTRY_PATH, safe='/')}"
    raw = github._request(
        "GET",
        f"{registry_api_path}?ref={quote(REGISTRY_BRANCH, safe='/')}",
    )
    registry = _decode_registry_content(raw)
    if str(registry.get("repository") or "") != settings.repository:
        raise GithubAuthorityError("REGISTRY_THAW_REPOSITORY_MISMATCH")
    if str(registry.get("registry_ref") or "") != f"refs/heads/{REGISTRY_BRANCH}":
        raise GithubAuthorityError("REGISTRY_THAW_REGISTRY_REF_MISMATCH")
    if str(registry.get("registry_path") or "") != REGISTRY_PATH:
        raise GithubAuthorityError("REGISTRY_THAW_REGISTRY_PATH_MISMATCH")
    if str(registry.get("state_hash") or "") != _registry_state_hash(registry):
        raise GithubAuthorityError("REGISTRY_THAW_STATE_HASH_INVALID")

    frozen = github._flatten_registry_artifacts(registry)
    if str(frozen.get(req.path) or "").lower() != req.from_blob:
        raise GithubAuthorityError("REGISTRY_THAW_FROZEN_OWNER_MISSING")

    active_before = copy.deepcopy(list(registry.get("active_thaws") or []))
    entries_before = copy.deepcopy(registry.get("entries"))
    previous_revision = int(registry.get("revision", -1))
    if previous_revision < 0:
        raise GithubAuthorityError("REGISTRY_THAW_REVISION_INVALID")
    previous_state_hash = str(registry["state_hash"])

    retarget_index: int | None = None
    for index, grant in enumerate(active_before):
        grant_id = str(grant.get("thaw_id") or "")
        files = grant.get("files") or {}
        pair = files.get(req.path) if isinstance(files, dict) else None
        if grant_id == req.thaw_id:
            same_path_and_baseline = (
                isinstance(files, dict)
                and set(files) == {req.path}
                and isinstance(pair, dict)
                and str(pair.get("from_blob") or "").lower() == req.from_blob
            )
            if not same_path_and_baseline:
                raise GithubAuthorityError("REGISTRY_THAW_ID_COLLISION")

            current_target = str(grant.get("target_head_sha") or "")
            current_to_blob = str(pair.get("to_blob") or "").lower()
            if current_target == req.candidate_sha:
                if current_to_blob != req.to_blob:
                    raise GithubAuthorityError("REGISTRY_THAW_ID_COLLISION")
                return _registry_thaw_result(
                    req,
                    registry,
                    previous_revision=previous_revision,
                    previous_state_hash=previous_state_hash,
                    registry_commit_sha=None,
                    reused=True,
                )

            # A reviewed candidate may legitimately change the destination blob.
            # The earlier exact-main/candidate tree checks already prove the new
            # blob pair, while this identity check keeps the same thaw ID bound to
            # exactly one frozen path and the same frozen baseline. Unrelated
            # grants are preserved and verified again after the registry CAS.
            retarget_index = index
            break
        if pair is not None:
            raise GithubAuthorityError("REGISTRY_THAW_PATH_CONFLICT")

    expected_grant = {
        "thaw_id": req.thaw_id,
        "status": "ACTIVE",
        "target_head_sha": req.candidate_sha,
        "files": {
            req.path: {
                "from_blob": req.from_blob,
                "to_blob": req.to_blob,
            }
        },
    }
    if retarget_index is None:
        active_target = active_before + [expected_grant]
    else:
        active_target = copy.deepcopy(active_before)
        active_target[retarget_index] = expected_grant

    registry["active_thaws"] = active_target
    registry["revision"] = previous_revision + 1
    registry["state_hash"] = _registry_state_hash(registry)

    content = base64.b64encode(
        (_canonical_json(registry) + "\n").encode("utf-8")
    ).decode("ascii")
    try:
        written = github._request(
            "PUT",
            registry_api_path,
            json={
                "message": f"Runless V2: exact-head thaw {req.thaw_id}",
                "content": content,
                "branch": REGISTRY_BRANCH,
                "sha": str(raw.get("sha") or ""),
            },
        )
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code in {409, 422}:
            raise GithubAuthorityError("STALE_REGISTRY_CAS") from exc
        raise

    commit_sha = str(((written or {}).get("commit") or {}).get("sha") or "") or None
    readback_raw = github._request(
        "GET",
        f"{registry_api_path}?ref={quote(REGISTRY_BRANCH, safe='/')}",
    )
    readback = _decode_registry_content(readback_raw)
    if str(readback.get("state_hash") or "") != _registry_state_hash(readback):
        raise GithubAuthorityError("REGISTRY_THAW_READBACK_HASH_MISMATCH")
    if int(readback.get("revision", -1)) != previous_revision + 1:
        raise GithubAuthorityError("REGISTRY_THAW_READBACK_REVISION_MISMATCH")
    if readback.get("entries") != entries_before:
        raise GithubAuthorityError("REGISTRY_THAW_UNRELATED_ENTRY_DRIFT")

    active_after = list(readback.get("active_thaws") or [])
    if retarget_index is None:
        if active_after[:-1] != active_before:
            raise GithubAuthorityError("REGISTRY_THAW_UNRELATED_ACTIVE_DRIFT")
        if not active_after or active_after[-1] != expected_grant:
            raise GithubAuthorityError("REGISTRY_THAW_READBACK_IDENTITY_MISMATCH")
    else:
        if len(active_after) != len(active_before):
            raise GithubAuthorityError("REGISTRY_THAW_RETARGET_COUNT_DRIFT")
        for index, prior_grant in enumerate(active_before):
            if index == retarget_index:
                continue
            if active_after[index] != prior_grant:
                raise GithubAuthorityError("REGISTRY_THAW_UNRELATED_ACTIVE_DRIFT")
        if active_after[retarget_index] != expected_grant:
            raise GithubAuthorityError("REGISTRY_THAW_READBACK_IDENTITY_MISMATCH")

    return _registry_thaw_result(
        req,
        readback,
        previous_revision=previous_revision,
        previous_state_hash=previous_state_hash,
        registry_commit_sha=commit_sha,
        reused=False,
    )


def _execute_registry_forward_port(
    req: RegistryForwardPortRequest,
    *,
    settings: Settings,
    github: Any,
) -> dict[str, Any]:
    if req.repository != settings.repository:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_REPOSITORY_MISMATCH")
    if req.from_blob == req.to_blob:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_NOOP_REJECTED")

    current_main = str(github.main_sha())
    if current_main != req.merged_main_sha:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_MAIN_IDENTITY_DRIFT")

    candidate_tree = github.tree_blobs(req.candidate_sha)
    merged_tree = github.tree_blobs(req.merged_main_sha)
    if str(candidate_tree.get(req.path) or "").lower() != req.to_blob:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_CANDIDATE_BLOB_MISMATCH")
    if str(merged_tree.get(req.path) or "").lower() != req.to_blob:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_MERGED_BLOB_MISMATCH")

    registry_api_path = f"/contents/{quote(REGISTRY_PATH, safe='/')}"
    raw = github._request(
        "GET",
        f"{registry_api_path}?ref={quote(REGISTRY_BRANCH, safe='/')}",
    )
    registry = _decode_registry_content(raw)
    if str(registry.get("repository") or "") != settings.repository:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_REPOSITORY_MISMATCH")
    if str(registry.get("registry_ref") or "") != f"refs/heads/{REGISTRY_BRANCH}":
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_REGISTRY_REF_MISMATCH")
    if str(registry.get("registry_path") or "") != REGISTRY_PATH:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_REGISTRY_PATH_MISMATCH")
    if str(registry.get("state_hash") or "") != _registry_state_hash(registry):
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_STATE_HASH_INVALID")

    entries_before = copy.deepcopy(registry.get("entries") or {})
    active_before = copy.deepcopy(list(registry.get("active_thaws") or []))
    previous_revision = int(registry.get("revision", -1))
    if previous_revision < 0:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_REVISION_INVALID")
    previous_state_hash = str(registry["state_hash"])

    matched_entries = 0
    for entry in entries_before.values():
        artifacts = entry.get("artifacts") if isinstance(entry, dict) else None
        if not isinstance(artifacts, dict) or req.path not in artifacts:
            continue
        matched_entries += 1
        if str(artifacts.get(req.path) or "").lower() != req.from_blob:
            raise GithubAuthorityError("REGISTRY_FORWARD_PORT_FROZEN_BASELINE_MISMATCH")
    if matched_entries == 0:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_FROZEN_OWNER_MISSING")

    thaw_index: int | None = None
    for index, grant in enumerate(active_before):
        files = grant.get("files") if isinstance(grant, dict) else None
        pair = files.get(req.path) if isinstance(files, dict) else None
        if str(grant.get("thaw_id") or "") == req.thaw_id:
            if str(grant.get("target_head_sha") or "") != req.candidate_sha:
                raise GithubAuthorityError("REGISTRY_FORWARD_PORT_THAW_IDENTITY_MISMATCH")
            if not (
                isinstance(pair, dict)
                and str(pair.get("from_blob") or "").lower() == req.from_blob
                and str(pair.get("to_blob") or "").lower() == req.to_blob
            ):
                raise GithubAuthorityError("REGISTRY_FORWARD_PORT_THAW_IDENTITY_MISMATCH")
            thaw_index = index
            continue
        if pair is not None:
            raise GithubAuthorityError("REGISTRY_FORWARD_PORT_PATH_CONFLICT")
    if thaw_index is None:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_THAW_IDENTITY_MISMATCH")

    target = copy.deepcopy(registry)
    for entry in target.get("entries", {}).values():
        artifacts = entry.get("artifacts") if isinstance(entry, dict) else None
        if isinstance(artifacts, dict) and req.path in artifacts:
            artifacts[req.path] = req.to_blob

    next_active: list[dict[str, Any]] = []
    for index, grant in enumerate(target.get("active_thaws") or []):
        if index != thaw_index:
            next_active.append(grant)
            continue
        kept = copy.deepcopy(grant)
        kept_files = dict(kept.get("files") or {})
        kept_files.pop(req.path, None)
        if kept_files:
            kept["files"] = kept_files
            next_active.append(kept)
    target["active_thaws"] = next_active
    target["source_main_sha"] = req.merged_main_sha
    target["revision"] = previous_revision + 1
    target["state_hash"] = _registry_state_hash(target)

    content = base64.b64encode(
        (_canonical_json(target) + "\n").encode("utf-8")
    ).decode("ascii")
    try:
        written = github._request(
            "PUT",
            registry_api_path,
            json={
                "message": f"registry: forward-port {req.workstream}",
                "content": content,
                "branch": REGISTRY_BRANCH,
                "sha": str(raw.get("sha") or ""),
            },
        )
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code in {409, 422}:
            raise GithubAuthorityError("STALE_REGISTRY_CAS") from exc
        raise

    commit_sha = str(((written or {}).get("commit") or {}).get("sha") or "") or None
    readback_raw = github._request(
        "GET",
        f"{registry_api_path}?ref={quote(REGISTRY_BRANCH, safe='/')}",
    )
    readback = _decode_registry_content(readback_raw)
    if str(readback.get("state_hash") or "") != _registry_state_hash(readback):
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_READBACK_HASH_MISMATCH")
    if int(readback.get("revision", -1)) != previous_revision + 1:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_READBACK_REVISION_MISMATCH")
    if str(readback.get("source_main_sha") or "") != req.merged_main_sha:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_READBACK_MAIN_MISMATCH")

    expected_entries = target.get("entries") or {}
    if readback.get("entries") != expected_entries:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_UNRELATED_ENTRY_DRIFT")
    if list(readback.get("active_thaws") or []) != next_active:
        raise GithubAuthorityError("REGISTRY_FORWARD_PORT_UNRELATED_ACTIVE_DRIFT")

    return {
        "thaw_id": req.thaw_id,
        "candidate_sha": req.candidate_sha,
        "merged_main_sha": req.merged_main_sha,
        "path": req.path,
        "from_blob": req.from_blob,
        "to_blob": req.to_blob,
        "previous_registry_revision": previous_revision,
        "current_registry_revision": int(readback["revision"]),
        "previous_state_hash": previous_state_hash,
        "current_state_hash": str(readback["state_hash"]),
        "registry_commit_sha": commit_sha,
        "state": "FROZEN",
        "retired": True,
        "failure_class": "NONE",
        "detail": "",
    }


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
    app.include_router(nba_pra_market_router)
    app.include_router(nba_pra_player_context_router)
    app.include_router(nba_pra_schedule_router)
    app.include_router(nba_pra_injury_router)
    app.include_router(nba_pra_matchup_router)
    app.include_router(wnba_pra_market_router)
    app.include_router(wnba_schedule_router)
    app.state.settings = cfg
    app.state.state_store = store
    app.state.github = gh
    app.state.sandbox = sandbox

    bearer = HTTPBearer(auto_error=False)

    def authenticated(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> None:
        authorization = None
        if credentials is not None:
            authorization = f"{credentials.scheme} {credentials.credentials}"
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

    @app.post("/supersede-base-drift", dependencies=[Depends(authenticated)])
    def supersede_base_drift(req: BaseDriftSupersessionRequest) -> dict[str, Any]:
        if not cfg.authority_enabled:
            raise HTTPException(status_code=503, detail="RUNLESS_V2_AUTHORITY_DISABLED")
        try:
            if req.repository != cfg.repository:
                raise RunlessV2StateError("RUNLESS_V2_SUPERSESSION_REPOSITORY_MISMATCH")

            before = store.status(req.old_proof_id)
            if (
                before.workstream != req.workstream
                or before.task_id != req.task_id
                or before.candidate_sha != req.old_candidate_sha
            ):
                raise RunlessV2StateError("RUNLESS_V2_SUPERSESSION_OLD_IDENTITY_MISMATCH")
            if before.state is not ProofState.MERGE_AUTHORIZED:
                raise RunlessV2StateError("RUNLESS_V2_SUPERSESSION_OLD_STATE_INVALID")
            if not before.receipt_digest or before.gate_check_run_id is None:
                raise RunlessV2StateError("RUNLESS_V2_SUPERSESSION_MISSING_EVIDENCE")
            if store.live_workstream_leases(req.workstream):
                raise RunlessV2StateError("RUNLESS_V2_SUPERSESSION_WORKSTREAM_BUSY")

            gh.verify_base_drift_successor(
                old_candidate_sha=req.old_candidate_sha,
                old_expected_main_sha=before.expected_main_sha,
                successor_candidate_sha=req.successor_candidate_sha,
                successor_expected_main_sha=req.successor_expected_main_sha,
                pr_number=req.pr_number,
                branch=req.branch,
            )

            store.supersede_base_drift_authority(
                workstream=req.workstream,
                task_id=req.task_id,
                old_proof_id=req.old_proof_id,
                old_candidate_sha=req.old_candidate_sha,
                successor_candidate_sha=req.successor_candidate_sha,
                successor_expected_main_sha=req.successor_expected_main_sha,
                github_pr_number=req.pr_number,
                github_branch=req.branch,
            )
            durable = store.authority_supersession(req.old_proof_id)
            after = store.status(req.old_proof_id)
            if (
                durable.workstream != req.workstream
                or durable.old_proof_id != req.old_proof_id
                or durable.old_candidate_sha != req.old_candidate_sha
                or durable.successor_candidate_sha != req.successor_candidate_sha
                or durable.successor_expected_main_sha != req.successor_expected_main_sha
                or durable.github_pr_number != req.pr_number
                or durable.github_branch != req.branch
                or durable.reason != "BASE_DRIFT"
            ):
                raise RunlessV2StateError("RUNLESS_V2_SUPERSESSION_READBACK_IDENTITY_MISMATCH")
            if (
                durable.old_receipt_digest != before.receipt_digest
                or durable.old_gate_check_run_id != before.gate_check_run_id
                or after.receipt_digest != before.receipt_digest
                or after.gate_check_run_id != before.gate_check_run_id
                or after.state is not ProofState.SUPERSEDED_BASE_DRIFT
            ):
                raise RunlessV2StateError("RUNLESS_V2_SUPERSESSION_READBACK_EVIDENCE_MISMATCH")
            return durable.model_dump(mode="json")
        except (RunlessV2StateError, GithubAuthorityError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"RUNLESS_V2_SUPERSESSION_UNAVAILABLE:{type(exc).__name__}",
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

    @app.post("/registry-thaw", dependencies=[Depends(authenticated)])
    def registry_thaw(req: RegistryThawRequest) -> dict[str, Any]:
        if not cfg.authority_enabled:
            raise HTTPException(status_code=503, detail="RUNLESS_V2_AUTHORITY_DISABLED")
        try:
            return _execute_registry_thaw(req, settings=cfg, github=gh)
        except (GithubAuthorityError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"RUNLESS_V2_REGISTRY_THAW_UNAVAILABLE:{type(exc).__name__}",
            ) from exc

    @app.post("/registry-forward-port", dependencies=[Depends(authenticated)])
    def registry_forward_port(req: RegistryForwardPortRequest) -> dict[str, Any]:
        if not cfg.authority_enabled:
            raise HTTPException(status_code=503, detail="RUNLESS_V2_AUTHORITY_DISABLED")
        try:
            return _execute_registry_forward_port(req, settings=cfg, github=gh)
        except (GithubAuthorityError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"RUNLESS_V2_REGISTRY_FORWARD_PORT_UNAVAILABLE:{type(exc).__name__}",
            ) from exc

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
    fallback.include_router(nba_pra_market_router)
    fallback.include_router(nba_pra_player_context_router)
    fallback.include_router(nba_pra_schedule_router)
    fallback.include_router(nba_pra_injury_router)
    fallback.include_router(nba_pra_matchup_router)
    fallback.include_router(wnba_pra_market_router)
    fallback.include_router(wnba_schedule_router)

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