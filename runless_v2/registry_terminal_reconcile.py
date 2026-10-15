from __future__ import annotations

import base64
import copy
import re
from typing import Any, Mapping, TYPE_CHECKING
from urllib.parse import quote

import httpx

from .models import RegistryForwardPortRequest
from .registry_thaw import (
    REGISTRY_BRANCH,
    REGISTRY_PATH,
    _canonical,
    _error,
    _read_snapshot,
    _validate_registry,
    registry_state_hash,
    request_registry_forward_port as _forward_port,
)

if TYPE_CHECKING:
    from .github_authority import GithubAuthority

FINALIZATION_LEDGER_BRANCH = "monster-finalization-ledger-v2"
FINALIZATION_RECORD_DIR = "devsystem/finalization_ledger_v2/records"


def _terminal_checkpoint_evidence(
    authority: GithubAuthority, request: RegistryForwardPortRequest
) -> tuple[str, dict[str, str]] | None:
    plan_path = f"devsystem/runless_proof_plans/{request.workstream}.json"
    try:
        plan = authority._content_json(plan_path, request.candidate_sha)
    except Exception:
        return None
    if (
        str(plan.get("task_id") or "") != request.workstream
        or str(plan.get("workstream") or "") != request.workstream
    ):
        raise _error("REGISTRY_FORWARD_PORT_PLAN_IDENTITY_MISMATCH")
    freeze_token = str(plan.get("freeze_token") or "").strip()
    artifact_paths = plan.get("artifacts")
    if not freeze_token or not isinstance(artifact_paths, list) or not artifact_paths:
        raise _error("REGISTRY_FORWARD_PORT_FREEZE_PLAN_INVALID")

    record_path = f"{FINALIZATION_RECORD_DIR}/{freeze_token}.json"
    try:
        record = authority._content_json(record_path, FINALIZATION_LEDGER_BRANCH)
    except Exception:
        return None
    if (
        str(record.get("workstream") or "") != request.workstream
        or str(record.get("freeze_token") or "") != freeze_token
        or str(record.get("candidate_sha") or "") != request.candidate_sha
        or str(record.get("merged_main_sha") or "") != request.merged_main_sha
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(record.get("proof_digest") or ""))
    ):
        raise _error("REGISTRY_FORWARD_PORT_FINALIZATION_IDENTITY_MISMATCH")

    tree = authority.tree_blobs(request.candidate_sha)
    # Canonical completion treats task ledgers as advisory metadata that may be
    # autohealed after freeze; never pin them into the immutable checkpoint.
    immutable_paths = sorted(
        {
            str(path)
            for path in artifact_paths
            if str(path) and not str(path).startswith("devsystem/task_ledgers/")
        }
    )
    if not immutable_paths:
        raise _error("REGISTRY_FORWARD_PORT_FREEZE_ARTIFACTS_REQUIRED")
    missing = [path for path in immutable_paths if path not in tree]
    if missing:
        raise _error("REGISTRY_FORWARD_PORT_FREEZE_ARTIFACT_MISSING:" + ",".join(missing))
    return freeze_token, {path: str(tree[path]).lower() for path in immutable_paths}


def _result(
    *, snapshot: Mapping[str, Any], registry: Mapping[str, Any], freeze_token: str | None,
    checkpoint_registered: bool, reused: bool, previous_revision: int | None = None,
    previous_hash: str | None = None,
) -> dict[str, Any]:
    revision = int(registry["revision"]); state_hash = str(registry["state_hash"])
    return {
        "state": "FROZEN", "reused": reused, "retired_thaw": True,
        "checkpoint_registered": checkpoint_registered, "freeze_token": freeze_token,
        "previous_registry_revision": revision if previous_revision is None else previous_revision,
        "current_registry_revision": revision,
        "previous_state_hash": state_hash if previous_hash is None else previous_hash,
        "current_state_hash": state_hash,
        "registry_commit_sha": snapshot["head_sha"],
    }


def request_registry_forward_port(authority: GithubAuthority, request: RegistryForwardPortRequest) -> dict[str, Any]:
    base = _forward_port(authority, request)
    if not (base.get("reused") is True and base.get("retired_thaw") is True):
        return base

    repository = str(getattr(authority.settings, "repository", ""))
    for attempt in range(2):
        snapshot = _read_snapshot(authority, repository=repository)
        registry = snapshot["registry"]
        revision = int(registry["revision"]); state_hash = str(registry["state_hash"])
        frozen = snapshot["frozen"]
        if frozen.get(request.path) != request.to_blob:
            raise _error("REGISTRY_FORWARD_PORT_RECONCILE_BASELINE_DRIFT")
        if any(g.get("thaw_id") == request.thaw_id for g in registry["active_thaws"]):
            raise _error("REGISTRY_FORWARD_PORT_RECONCILE_THAW_NOT_RETIRED")
        if str(registry.get("source_main_sha") or "") != request.merged_main_sha:
            raise _error("REGISTRY_FORWARD_PORT_RECONCILE_SOURCE_MAIN_DRIFT")

        evidence = _terminal_checkpoint_evidence(authority, request)
        if evidence is None:
            return _result(snapshot=snapshot, registry=registry, freeze_token=None,
                           checkpoint_registered=False, reused=True)
        freeze_token, artifacts = evidence
        expected_entry = {
            "status": "FROZEN", "checkpoint_id": freeze_token,
            "source_main_sha": request.merged_main_sha,
            "artifacts": dict(sorted(artifacts.items())),
        }
        existing = (registry.get("entries") or {}).get(freeze_token)
        if existing is not None:
            if existing != expected_entry:
                raise _error("REGISTRY_FORWARD_PORT_FREEZE_TOKEN_COLLISION")
            return _result(snapshot=snapshot, registry=registry, freeze_token=freeze_token,
                           checkpoint_registered=False, reused=True)

        updated = copy.deepcopy(registry)
        thaws_before = copy.deepcopy(registry["active_thaws"])
        entries_before = copy.deepcopy(registry["entries"])
        updated["entries"][freeze_token] = expected_entry
        updated["revision"] = revision + 1
        updated["state_hash"] = registry_state_hash(updated)
        _validate_registry(updated, repository=repository)
        text = _canonical(updated) + "\n"
        try:
            written = authority._request(
                "PUT", f"/contents/{quote(REGISTRY_PATH, safe='/')}",
                json={"message": f"registry: freeze {freeze_token}",
                      "content": base64.b64encode(text.encode()).decode("ascii"),
                      "branch": REGISTRY_BRANCH, "sha": snapshot["blob_sha"]},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (409, 422) and attempt == 0:
                continue
            if exc.response.status_code in (409, 422):
                raise _error("STALE_REGISTRY_CAS") from exc
            raise
        commit_sha = str(((written or {}).get("commit") or {}).get("sha") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            raise _error("REGISTRY_FORWARD_PORT_FREEZE_CONTENTS_WRITE_FAILED")
        readback = _read_snapshot(authority, repository=repository)
        current = readback["registry"]
        if readback["head_sha"] != commit_sha:
            raise _error("REGISTRY_FORWARD_PORT_FREEZE_READBACK_HEAD_MISMATCH")
        if int(current["revision"]) != revision + 1:
            raise _error("REGISTRY_FORWARD_PORT_FREEZE_READBACK_REVISION_MISMATCH")
        if current["active_thaws"] != thaws_before:
            raise _error("REGISTRY_FORWARD_PORT_FREEZE_UNRELATED_THAW_DRIFT")
        if {k: v for k, v in current["entries"].items() if k != freeze_token} != entries_before:
            raise _error("REGISTRY_FORWARD_PORT_FREEZE_UNRELATED_ENTRY_DRIFT")
        if current["entries"].get(freeze_token) != expected_entry:
            raise _error("REGISTRY_FORWARD_PORT_FREEZE_READBACK_MISMATCH")
        return _result(snapshot=readback, registry=current, freeze_token=freeze_token,
                       checkpoint_registered=True, reused=False,
                       previous_revision=revision, previous_hash=state_hash)
    raise _error("STALE_REGISTRY_CAS")
