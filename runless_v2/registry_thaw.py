from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
from pathlib import PurePosixPath
from typing import Any, Mapping, TYPE_CHECKING
from urllib.parse import quote

import httpx

from .models import RegistryThawRequest

if TYPE_CHECKING:
    from .github_authority import GithubAuthority

REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_REF = f"refs/heads/{REGISTRY_BRANCH}"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
REGISTRY_VERSION = "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _error(code: str) -> RuntimeError:
    from .github_authority import GithubAuthorityError

    return GithubAuthorityError(code)


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def registry_state_hash(payload: Mapping[str, Any]) -> str:
    value = copy.deepcopy(dict(payload))
    value.pop("state_hash", None)
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _validate_registry(payload: Mapping[str, Any], *, repository: str) -> dict[str, str]:
    if not isinstance(payload, Mapping):
        raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
    registry = dict(payload)
    required = {
        "schema_version",
        "version",
        "repository",
        "registry_ref",
        "registry_path",
        "revision",
        "source_main_sha",
        "entries",
        "active_thaws",
        "state_hash",
    }
    if required - set(registry):
        raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
    if int(registry["schema_version"]) != 1 or registry["version"] != REGISTRY_VERSION:
        raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
    if registry["repository"] != repository:
        raise _error("REGISTRY_THAW_REGISTRY_REPOSITORY_MISMATCH")
    if registry["registry_ref"] != REGISTRY_REF or registry["registry_path"] != REGISTRY_PATH:
        raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
    try:
        revision = int(registry["revision"])
    except Exception as exc:
        raise _error("REGISTRY_THAW_REGISTRY_REVISION_INVALID") from exc
    if revision < 0 or not _SHA40.fullmatch(str(registry["source_main_sha"] or "")):
        raise _error("REGISTRY_THAW_REGISTRY_REVISION_INVALID")

    entries = registry["entries"]
    if not isinstance(entries, Mapping) or not entries:
        raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
    flattened: dict[str, str] = {}
    for checkpoint, entry in entries.items():
        if not isinstance(entry, Mapping):
            raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
        if entry.get("status") != "FROZEN" or str(entry.get("checkpoint_id") or "") != str(checkpoint):
            raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
        if not _SHA40.fullmatch(str(entry.get("source_main_sha") or "")):
            raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
        artifacts = entry.get("artifacts")
        if not isinstance(artifacts, Mapping) or not artifacts:
            raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
        for raw_path, raw_blob in artifacts.items():
            path = str(raw_path or "").strip()
            blob = str(raw_blob or "").strip().lower()
            parts = PurePosixPath(path).parts
            if not path or path.startswith("/") or ".." in parts or not _SHA40.fullmatch(blob):
                raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
            prior = flattened.get(path)
            if prior is not None and prior != blob:
                raise _error("REGISTRY_THAW_FROZEN_BASELINE_CONFLICT")
            flattened[path] = blob

    thaws = registry["active_thaws"]
    if not isinstance(thaws, list):
        raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
    seen_ids: set[str] = set()
    for grant in thaws:
        if not isinstance(grant, Mapping):
            raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
        thaw_id = str(grant.get("thaw_id") or "").strip()
        if not thaw_id or thaw_id in seen_ids or grant.get("status") != "ACTIVE":
            raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
        seen_ids.add(thaw_id)
        if not _SHA40.fullmatch(str(grant.get("target_head_sha") or "")):
            raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
        files = grant.get("files")
        if not isinstance(files, Mapping) or not files:
            raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
        for path, pair in files.items():
            if path not in flattened or not isinstance(pair, Mapping):
                raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")
            before = str(pair.get("from_blob") or "").lower()
            after = str(pair.get("to_blob") or "").lower()
            if before != flattened[path] or not _SHA40.fullmatch(after) or after == before:
                raise _error("REGISTRY_THAW_REGISTRY_SCHEMA_INVALID")

    if str(registry.get("state_hash") or "") != registry_state_hash(registry):
        raise _error("REGISTRY_THAW_REGISTRY_STATE_HASH_INVALID")
    return flattened


def _read_snapshot(authority: GithubAuthority, *, repository: str) -> dict[str, Any]:
    ref = authority._request("GET", f"/git/ref/heads/{quote(REGISTRY_BRANCH, safe='/')}")
    head_sha = str(((ref or {}).get("object") or {}).get("sha") or "")
    if not _SHA40.fullmatch(head_sha):
        raise _error("REGISTRY_THAW_REGISTRY_REF_INVALID")
    raw = authority._request(
        "GET",
        f"/contents/{quote(REGISTRY_PATH, safe='/')}?ref={quote(REGISTRY_BRANCH, safe='/')}",
    )
    if not raw or raw.get("encoding") != "base64" or not _SHA40.fullmatch(str(raw.get("sha") or "")):
        raise _error("REGISTRY_THAW_REGISTRY_READ_FAILED")
    try:
        registry = json.loads(base64.b64decode(raw["content"]).decode("utf-8"))
    except Exception as exc:
        raise _error("REGISTRY_THAW_REGISTRY_READ_FAILED") from exc
    frozen = _validate_registry(registry, repository=repository)
    return {
        "head_sha": head_sha,
        "blob_sha": str(raw["sha"]),
        "registry": registry,
        "frozen": frozen,
    }


def _exact_grant(request: RegistryThawRequest) -> dict[str, Any]:
    return {
        "thaw_id": request.thaw_id,
        "status": "ACTIVE",
        "target_head_sha": request.candidate_sha,
        "files": {
            request.path: {
                "from_blob": request.from_blob,
                "to_blob": request.to_blob,
            }
        },
    }


def _same_grant(value: Mapping[str, Any], request: RegistryThawRequest) -> bool:
    return dict(value) == _exact_grant(request)


def _success(
    request: RegistryThawRequest,
    *,
    previous_revision: int,
    current_revision: int,
    previous_hash: str,
    current_hash: str,
    registry_commit_sha: str,
    reused: bool,
) -> dict[str, Any]:
    return {
        "thaw_id": request.thaw_id,
        "target_head_sha": request.candidate_sha,
        "path": request.path,
        "from_blob": request.from_blob,
        "to_blob": request.to_blob,
        "previous_registry_revision": previous_revision,
        "current_registry_revision": current_revision,
        "previous_state_hash": previous_hash,
        "current_state_hash": current_hash,
        "registry_commit_sha": registry_commit_sha,
        "state": "ACTIVE",
        "reused": reused,
        "failure_class": "NONE",
        "detail": "",
    }


def request_registry_thaw(authority: GithubAuthority, request: RegistryThawRequest) -> dict[str, Any]:
    repository = str(getattr(authority.settings, "repository", ""))
    if request.repository != repository:
        raise _error("REGISTRY_THAW_REPOSITORY_MISMATCH")
    candidate = authority.commit(request.candidate_sha)
    if str((candidate or {}).get("sha") or "") != request.candidate_sha:
        raise _error("REGISTRY_THAW_CANDIDATE_IDENTITY_MISMATCH")
    if authority.main_sha() != request.expected_main_sha:
        raise _error("REGISTRY_THAW_MAIN_IDENTITY_DRIFT")
    if request.from_blob == request.to_blob:
        raise _error("REGISTRY_THAW_TO_BLOB_INVALID")
    candidate_tree = authority.tree_blobs(request.candidate_sha)

    stale_seen = False
    for attempt in range(2):
        snapshot = _read_snapshot(authority, repository=repository)
        registry = snapshot["registry"]
        frozen = snapshot["frozen"]
        revision = int(registry["revision"])
        state_hash = str(registry["state_hash"])

        baseline = frozen.get(request.path)
        if baseline is None:
            raise _error("REGISTRY_THAW_PATH_NOT_FROZEN")
        if baseline != request.from_blob:
            raise _error("REGISTRY_THAW_FROM_BLOB_MISMATCH")
        if candidate_tree.get(request.path) != request.to_blob:
            raise _error("REGISTRY_THAW_TO_BLOB_MISMATCH")

        for grant in registry["active_thaws"]:
            if grant.get("thaw_id") == request.thaw_id:
                if _same_grant(grant, request):
                    return _success(
                        request,
                        previous_revision=revision,
                        current_revision=revision,
                        previous_hash=state_hash,
                        current_hash=state_hash,
                        registry_commit_sha=snapshot["head_sha"],
                        reused=True,
                    )
                raise _error("REGISTRY_THAW_IDENTITY_COLLISION")
            if request.path in (grant.get("files") or {}):
                raise _error("REGISTRY_THAW_PATH_CONFLICT")

        updated = copy.deepcopy(registry)
        updated["active_thaws"].append(_exact_grant(request))
        updated["revision"] = revision + 1
        updated["state_hash"] = registry_state_hash(updated)
        _validate_registry(updated, repository=repository)
        content = (_canonical(updated) + "\n").encode("utf-8")

        blob = authority._request(
            "POST",
            "/git/blobs",
            json={"content": base64.b64encode(content).decode("ascii"), "encoding": "base64"},
        )
        blob_sha = str((blob or {}).get("sha") or "")
        if not _SHA40.fullmatch(blob_sha):
            raise _error("REGISTRY_THAW_GIT_BLOB_WRITE_FAILED")
        parent = authority.commit(snapshot["head_sha"])
        tree_sha = str((((parent or {}).get("commit") or {}).get("tree") or {}).get("sha") or "")
        if not _SHA40.fullmatch(tree_sha):
            raise _error("REGISTRY_THAW_REGISTRY_PARENT_INVALID")
        tree = authority._request(
            "POST",
            "/git/trees",
            json={
                "base_tree": tree_sha,
                "tree": [{"path": REGISTRY_PATH, "mode": "100644", "type": "blob", "sha": blob_sha}],
            },
        )
        next_tree = str((tree or {}).get("sha") or "")
        commit = authority._request(
            "POST",
            "/git/commits",
            json={
                "message": f"runless registry thaw: {request.thaw_id}",
                "tree": next_tree,
                "parents": [snapshot["head_sha"]],
            },
        )
        commit_sha = str((commit or {}).get("sha") or "")
        if not _SHA40.fullmatch(commit_sha):
            raise _error("REGISTRY_THAW_GIT_COMMIT_FAILED")
        try:
            authority._request(
                "PATCH",
                f"/git/refs/heads/{quote(REGISTRY_BRANCH, safe='/')}",
                json={"sha": commit_sha, "force": False},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (409, 422):
                stale_seen = True
                if attempt == 0:
                    continue
                raise _error("STALE_REGISTRY_CAS") from exc
            raise

        readback = _read_snapshot(authority, repository=repository)
        if readback["head_sha"] != commit_sha:
            raise _error("REGISTRY_THAW_READBACK_HEAD_MISMATCH")
        current = readback["registry"]
        matches = [grant for grant in current["active_thaws"] if grant.get("thaw_id") == request.thaw_id]
        if len(matches) != 1 or not _same_grant(matches[0], request):
            raise _error("REGISTRY_THAW_READBACK_MISMATCH")
        if int(current["revision"]) != revision + 1:
            raise _error("REGISTRY_THAW_READBACK_REVISION_MISMATCH")
        return _success(
            request,
            previous_revision=revision,
            current_revision=int(current["revision"]),
            previous_hash=state_hash,
            current_hash=str(current["state_hash"]),
            registry_commit_sha=commit_sha,
            reused=False,
        )

    if stale_seen:
        raise _error("STALE_REGISTRY_CAS")
    raise _error("REGISTRY_THAW_UNREACHABLE")
