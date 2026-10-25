"""API2 Step 2A one-problem/one-path and one-use repair authority."""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Mapping

from devsystem.api2_isolation_guard_v1 import validate_api2_authority

VERSION = "API2_STEP2A_AUTHORITY_V2"
API2_REPOSITORY = "kyrepeak/kyre-sports-ai"
API2_BASE_REF = "refs/heads/api2-main"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DEPLOYMENT_ID = re.compile(r"^dpl_[A-Za-z0-9]{20,}$")


class Step2AError(RuntimeError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _authority_digest(active_problem: Mapping[str, Any]) -> str:
    return "sha256:" + _digest(dict(active_problem))


def _strict_identity_requested(values: tuple[Any, ...]) -> bool:
    return any(value is not None for value in values)


def begin_problem(
    state: Mapping[str, Any],
    *,
    problem_id: str,
    branch: str,
    proof_path: str,
    repository: str | None = None,
    base_ref: str | None = None,
    base_sha: str | None = None,
    pr_number: int | None = None,
    run_id: str | None = None,
    deployment_id: str | None = None,
) -> dict[str, Any]:
    """Bind exactly one API2 problem/path.

    Legacy callers that provide only problem/branch/proof_path retain their old
    shape. Real execution handoffs use strict mode by supplying execution
    identity; strict mode requires the complete repo/base/PR/run/deployment path
    and makes that identity tamper evident.
    """
    strict = _strict_identity_requested(
        (repository, base_ref, base_sha, pr_number, run_id, deployment_id)
    )
    if strict:
        if repository != API2_REPOSITORY:
            raise Step2AError("API2_REPOSITORY_IDENTITY_MISMATCH")
        if base_ref != API2_BASE_REF:
            raise Step2AError("API2_BASE_REF_MISMATCH")
        if not isinstance(base_sha, str) or not _SHA40.fullmatch(base_sha):
            raise Step2AError("API2_BASE_SHA_INVALID")
        if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number <= 0:
            raise Step2AError("API2_PR_NUMBER_INVALID")
        if not isinstance(run_id, str) or not run_id.startswith("api2-"):
            raise Step2AError("API2_RUN_ID_INVALID")
        if not isinstance(deployment_id, str) or not _DEPLOYMENT_ID.fullmatch(deployment_id):
            raise Step2AError("API2_DEPLOYMENT_ID_INVALID")
        requested = {
            "system": "api2",
            "problem_id": problem_id,
            "repository": repository,
            "base_ref": base_ref,
            "base_sha": base_sha,
            "branch": branch,
            "pr_number": pr_number,
            "run_id": run_id,
            "deployment_id": deployment_id,
            "proof_path": proof_path,
        }
    else:
        requested = {
            "problem_id": problem_id,
            "branch": branch,
            "proof_path": proof_path,
        }

    validate_api2_authority(
        {
            "system": "api2",
            "problem_id": problem_id,
            "branch": branch,
            "proof_path": proof_path,
            **({"base_ref": base_ref} if base_ref is not None else {}),
        }
    )
    out = deepcopy(dict(state))
    active = out.get("active_problem")
    if active and active != requested:
        raise Step2AError("API2_MULTIPLE_ACTIVE_PROBLEMS_OR_PATHS_FORBIDDEN")

    out["active_problem"] = deepcopy(requested)
    out.setdefault("consumed_authorizations", [])
    digest = _authority_digest(requested)
    existing_digest = out.get("authority_digest")
    if existing_digest is not None and existing_digest != digest:
        raise Step2AError("API2_AUTHORITY_DIGEST_DRIFT")
    out["authority_digest"] = digest
    out["strict_authority"] = strict
    return out


def authority_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    active = deepcopy(dict(state.get("active_problem") or {}))
    if not active:
        raise Step2AError("API2_NO_ACTIVE_PROBLEM")
    digest = _authority_digest(active)
    if state.get("authority_digest") != digest:
        raise Step2AError("API2_AUTHORITY_SNAPSHOT_DIGEST_MISMATCH")
    return {
        "version": VERSION,
        "active_problem": active,
        "consumed_authorizations": list(state.get("consumed_authorizations") or []),
        "authority_digest": digest,
        "strict_authority": bool(state.get("strict_authority")),
    }


def restore_authority(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    data = deepcopy(dict(snapshot))
    active = dict(data.get("active_problem") or {})
    stored = str(data.get("authority_digest") or "")
    if not active or stored != _authority_digest(active):
        raise Step2AError("API2_AUTHORITY_SNAPSHOT_DIGEST_MISMATCH")
    validate_api2_authority(
        {
            "system": active.get("system", "api2"),
            "problem_id": active.get("problem_id"),
            "branch": active.get("branch"),
            "proof_path": active.get("proof_path"),
            **({"base_ref": active.get("base_ref")} if active.get("base_ref") else {}),
        }
    )
    if data.get("strict_authority"):
        if active.get("repository") != API2_REPOSITORY:
            raise Step2AError("API2_REPOSITORY_IDENTITY_MISMATCH")
        if active.get("base_ref") != API2_BASE_REF:
            raise Step2AError("API2_BASE_REF_MISMATCH")
        if not _SHA40.fullmatch(str(active.get("base_sha") or "")):
            raise Step2AError("API2_BASE_SHA_INVALID")
        if not _DEPLOYMENT_ID.fullmatch(str(active.get("deployment_id") or "")):
            raise Step2AError("API2_DEPLOYMENT_ID_INVALID")
    return {
        "active_problem": active,
        "consumed_authorizations": list(data.get("consumed_authorizations") or []),
        "authority_digest": stored,
        "strict_authority": bool(data.get("strict_authority")),
    }


def authorize_repair(
    state: Mapping[str, Any],
    *,
    repair: Mapping[str, Any],
    reliability: Mapping[str, Any],
    anti_loop: Mapping[str, Any],
) -> dict[str, Any]:
    if not state.get("active_problem"):
        raise Step2AError("API2_NO_ACTIVE_PROBLEM")
    if state.get("authority_digest") != _authority_digest(state["active_problem"]):
        raise Step2AError("API2_AUTHORITY_DIGEST_DRIFT")
    if reliability.get("allowed") is not True:
        raise Step2AError("API2_STEP2B_NOT_GREEN")
    if anti_loop.get("allowed") is not True:
        raise Step2AError("API2_ANTI_LOOP_NOT_SATISFIED")
    payload = {
        "system": "api2",
        "path": state["active_problem"],
        "authority_digest": state["authority_digest"],
        "repair": dict(repair),
        "step2b": reliability.get("decision_digest"),
        "anti_loop": anti_loop.get("decision"),
    }
    return {
        **payload,
        "authorization_id": "API2-AUTH-" + _digest(payload)[:24],
        "single_use": True,
    }


def consume_authorization(
    state: Mapping[str, Any], authorization: Mapping[str, Any]
) -> dict[str, Any]:
    out = deepcopy(dict(state))
    if authorization.get("authority_digest") != out.get("authority_digest"):
        raise Step2AError("API2_AUTHORIZATION_AUTHORITY_MISMATCH")
    consumed = list(out.get("consumed_authorizations") or [])
    auth_id = str(authorization.get("authorization_id") or "")
    if not auth_id or auth_id in consumed:
        raise Step2AError("API2_AUTHORIZATION_ALREADY_USED_OR_INVALID")
    consumed.append(auth_id)
    out["consumed_authorizations"] = consumed
    return out
