"""API2-isolated Step 2A authority routing for Runless V2.

For api2-* workstreams targeting protected ``main``, route scope-lease and
frozen-registry reads only to API2-owned live-main control-state branches.
Legacy/non-API2 workstreams retain the existing Runless authority methods
unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from . import github_authority as _gha
from .models import ProofRequest

API2_LEASE_BRANCH = "api2-scope-aware-execution-leases"
API2_LEASE_PATH = "devsystem/api2_scope_lease_state_v1.json"
API2_REGISTRY_BRANCH = "api2-live-main-frozen-registry"
API2_REGISTRY_PATH = "devsystem/api2_live_main_frozen_registry_state_v1.json"
API2_REGISTRY_VERSION = "API2_FROZEN_ARTIFACT_REGISTRY_V1"
API2_TARGET_BASE_REF = "refs/heads/main"


def _is_api2_workstream(workstream: str) -> bool:
    return str(workstream or "").startswith("api2-")


def _api2_state_hash(payload: dict[str, Any]) -> str:
    value = copy.deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_live_scope_lease_for_workstream(self, workstream: str, lease_id: str) -> dict[str, Any]:
    if not _is_api2_workstream(workstream):
        return self.read_live_scope_lease(lease_id)

    state = self._content_json(API2_LEASE_PATH, API2_LEASE_BRANCH)
    if (
        str(state.get("system") or "") != "api2"
        or str(state.get("repository") or "") != self.settings.repository
        or str(state.get("lease_ref") or "") != f"refs/heads/{API2_LEASE_BRANCH}"
        or str(state.get("lease_state_path") or "") != API2_LEASE_PATH
    ):
        raise _gha.GithubAuthorityError("RUNLESS_V2_API2_SCOPE_AUTHORITY_INVALID")
    if str(state.get("state_hash") or "") != _api2_state_hash(state):
        raise _gha.GithubAuthorityError("RUNLESS_V2_API2_SCOPE_STATE_HASH_INVALID")

    now = datetime.now(timezone.utc)
    matches = [
        dict(holder)
        for holder in state.get("holders", [])
        if holder.get("lease_id") == lease_id
        and now < self._utc(holder["expires_at_utc"])
    ]
    if len(matches) != 1:
        raise _gha.GithubAuthorityError("RUNLESS_V2_API2_SCOPE_LEASE_NOT_LIVE")
    holder = matches[0]
    if not str(holder.get("owner_id") or "").startswith("chatgpt:api2:"):
        raise _gha.GithubAuthorityError("RUNLESS_V2_API2_SCOPE_OWNER_INVALID")
    dependency_tokens = set((holder.get("scope") or {}).get("dependency_tokens") or [])
    if "system:api2" not in dependency_tokens:
        raise _gha.GithubAuthorityError("RUNLESS_V2_API2_SCOPE_SYSTEM_TOKEN_MISSING")
    return holder


def _read_frozen_registry_for_workstream(self, workstream: str) -> dict[str, Any]:
    if not _is_api2_workstream(workstream):
        return self.read_frozen_registry()

    registry = self._content_json(API2_REGISTRY_PATH, API2_REGISTRY_BRANCH)
    if (
        str(registry.get("system") or "") != "api2"
        or str(registry.get("repository") or "") != self.settings.repository
        or str(registry.get("base_ref") or "") != API2_TARGET_BASE_REF
        or str(registry.get("registry_ref") or "") != f"refs/heads/{API2_REGISTRY_BRANCH}"
        or str(registry.get("registry_path") or "") != API2_REGISTRY_PATH
        or str(registry.get("version") or "") != API2_REGISTRY_VERSION
    ):
        raise _gha.GithubAuthorityError("RUNLESS_V2_API2_REGISTRY_AUTHORITY_INVALID")
    if str(registry.get("state_hash") or "") != _api2_state_hash(registry):
        raise _gha.GithubAuthorityError("RUNLESS_V2_API2_REGISTRY_STATE_HASH_INVALID")
    return registry


def _verify_step2a_api2_isolated(
    self,
    request: ProofRequest,
    plan: Any,
    candidate_tree: dict[str, str],
    main_tree: dict[str, str],
) -> dict[str, Any]:
    commit = self.commit(request.candidate_sha)
    if str(commit.get("sha") or "") != request.candidate_sha:
        raise _gha.GithubAuthorityError("RUNLESS_V2_EXACT_HEAD_DRIFT")
    if self._plan_value(plan, "workstream") != request.workstream:
        raise _gha.GithubAuthorityError("RUNLESS_V2_PLAN_WORKSTREAM_MISMATCH")

    is_api2 = _is_api2_workstream(request.workstream)
    if is_api2:
        if self._plan_value(plan, "authorization_id") != request.authorization_id:
            raise _gha.GithubAuthorityError("RUNLESS_V2_API2_AUTHORIZATION_MISMATCH")
        if self._plan_value(plan, "scope_lease_id") != request.lease_id:
            raise _gha.GithubAuthorityError("RUNLESS_V2_API2_SCOPE_LEASE_ID_MISMATCH")

    main_sha = self.main_sha()
    if request.expected_main_sha and main_sha != request.expected_main_sha:
        raise _gha.GithubAuthorityError("RUNLESS_V2_MAIN_IDENTITY_DRIFT")

    scope_lease = self._read_live_scope_lease_for_workstream(request.workstream, request.lease_id)
    registry = self._read_frozen_registry_for_workstream(request.workstream)
    self._verify_frozen_candidate(request.candidate_sha, candidate_tree, main_sha, main_tree, registry)
    artifacts = tuple(self._plan_value(plan, "artifacts", ()))
    dependencies = tuple(self._plan_value(plan, "dependencies", ()))
    return {
        "candidate_sha": request.candidate_sha,
        "main_sha": main_sha,
        "authority_system": "api2" if is_api2 else "legacy",
        "scope_lease": scope_lease,
        "registry": {
            "revision": registry.get("revision"),
            "state_hash": registry.get("state_hash"),
            "active_thaws": [item.get("thaw_id") for item in registry.get("active_thaws", [])],
        },
        "artifact_map": self._path_map(candidate_tree, artifacts, "ARTIFACT"),
        "dependency_map": self._path_map(candidate_tree, dependencies, "DEPENDENCY"),
    }


# Additive compatibility composition. Export API2 identities on the original
# module so existing imports/tests can observe the selected authority without
# replacing legacy constants or methods.
_gha.API2_LEASE_BRANCH = API2_LEASE_BRANCH
_gha.API2_LEASE_PATH = API2_LEASE_PATH
_gha.API2_REGISTRY_BRANCH = API2_REGISTRY_BRANCH
_gha.API2_REGISTRY_PATH = API2_REGISTRY_PATH
_gha.GithubAuthority._read_live_scope_lease_for_workstream = _read_live_scope_lease_for_workstream
_gha.GithubAuthority._read_frozen_registry_for_workstream = _read_frozen_registry_for_workstream
_gha.GithubAuthority.verify_step2a = _verify_step2a_api2_isolated
