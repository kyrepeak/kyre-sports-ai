from __future__ import annotations

import base64
import json
import os
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import _hash as registry_hash
from devsystem.frozen_artifact_registry_v1 import _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    release_scope,
    validate_state,
)

from .models import ProofRequest
from .prove import execute_proof_request
from .registry import GithubRegistryBackend, REGISTRY_PATH

ENV_TRIGGER = "RPP_NBA_SPREAD_STEP3_PROVE_ON_START"
ENV_CANDIDATE = "RPP_NBA_SPREAD_STEP3_CANDIDATE_SHA"
TASK_ID = "nba-spread-step3-schedule-phoenix-v1"
WORKSTREAM = "nba-spread-two-page-v1"
BRANCH = "nba-spread-step3-schedule-phoenix-r1"
SOURCE_MAIN_SHA = "30e803ea943091d07e760d9d4e003e110cbc29ed"
AUTHORIZATION_ID = "AUTH-NBA-SPREAD-STEP3-SCHEDULE-PHOENIX-R1"
THAW_ID = "THAW-NBA-SPREAD-STEP3-SCHEDULE-PHOENIX-R1"
OWNER_ID = "chatgpt:api2:nba-spread-step3-schedule-phoenix-v1"
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
ALLOWED_PATHS = {
    "devsystem/execution_plans/nba-spread-step3-schedule-phoenix-v1.json",
    "devsystem/runless_proof_plans/nba-spread-step3-schedule-phoenix-v1.json",
    "devsystem/task_ledgers/nba-spread-step3-schedule-phoenix-v1.json",
    "nba_spread_schedule_v1.py",
    "nba_spread_page_v1.py",
    "tests/test_nba_spread_step3_schedule_phoenix_v1.py",
}


class NBAGroupStep3AuthorityFailure(RuntimeError):
    pass


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise NBAGroupStep3AuthorityFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise NBAGroupStep3AuthorityFailure(label + "_DECODE_FAILED") from exc


def _candidate() -> str:
    value = os.environ.get(ENV_CANDIDATE, "").strip().lower()
    if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        raise NBAGroupStep3AuthorityFailure("NBA_STEP3_CANDIDATE_ENV_INVALID")
    return value


def _changed_paths(client, candidate_sha: str) -> tuple[tuple[str, ...], dict[str, str], dict[str, str]]:
    if client.branch_sha("main") != SOURCE_MAIN_SHA:
        raise NBAGroupStep3AuthorityFailure("NBA_STEP3_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != candidate_sha:
        raise NBAGroupStep3AuthorityFailure("NBA_STEP3_BRANCH_HEAD_DRIFT")

    main_tree = client.tree_blobs(SOURCE_MAIN_SHA)
    candidate_tree = client.tree_blobs(candidate_sha)
    changed = tuple(
        sorted(
            path
            for path in set(main_tree) | set(candidate_tree)
            if main_tree.get(path) != candidate_tree.get(path)
        )
    )
    unexpected = sorted(set(changed) - ALLOWED_PATHS)
    if unexpected:
        raise NBAGroupStep3AuthorityFailure(
            "NBA_STEP3_SCOPE_ESCAPE:" + ",".join(unexpected)
        )
    if not changed:
        raise NBAGroupStep3AuthorityFailure("NBA_STEP3_EMPTY_CANDIDATE")
    return changed, main_tree, candidate_tree


def _prepare_registry(client, candidate_sha: str, changed: tuple[str, ...], main_tree: dict[str, str], candidate_tree: dict[str, str]):
    backend = GithubRegistryBackend(client)
    current = backend.read_registry()
    validated = validate_registry(current)
    if str(current.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        raise NBAGroupStep3AuthorityFailure("NBA_STEP3_REGISTRY_MAIN_DRIFT")

    frozen = validated["artifacts"]
    thaw_files: dict[str, dict[str, str]] = {}
    for path in changed:
        if path not in frozen:
            continue
        expected = str(frozen[path])
        before = str(main_tree.get(path) or "")
        after = str(candidate_tree.get(path) or "")
        if before != expected:
            raise NBAGroupStep3AuthorityFailure("NBA_STEP3_FROZEN_BASELINE_DRIFT:" + path)
        if not after:
            raise NBAGroupStep3AuthorityFailure("NBA_STEP3_FROZEN_ARTIFACT_DELETED:" + path)
        thaw_files[path] = {"from_blob": expected, "to_blob": after}

    matches = [
        i for i, item in enumerate(current.get("active_thaws", []))
        if item.get("thaw_id") == THAW_ID
    ]
    if len(matches) > 1:
        raise NBAGroupStep3AuthorityFailure("NBA_STEP3_DUPLICATE_THAW_ID")

    if not thaw_files:
        if matches:
            raise NBAGroupStep3AuthorityFailure("NBA_STEP3_UNEXPECTED_EXISTING_THAW")
        return current, thaw_files

    exact = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": candidate_sha,
        "files": deepcopy(thaw_files),
    }
    if matches and current["active_thaws"][matches[0]] == exact:
        return current, thaw_files

    updated = deepcopy(current)
    if matches:
        previous = updated["active_thaws"][matches[0]]
        previous_files = previous.get("files") or {}
        if set(previous_files) != set(thaw_files):
            raise NBAGroupStep3AuthorityFailure("NBA_STEP3_THAW_FILESET_DRIFT")
        for path, pair in thaw_files.items():
            prior_pair = previous_files.get(path) or {}
            if str(prior_pair.get("from_blob") or "") != pair["from_blob"]:
                raise NBAGroupStep3AuthorityFailure("NBA_STEP3_THAW_BASELINE_DRIFT:" + path)
        updated["active_thaws"][matches[0]] = exact
    else:
        updated.setdefault("active_thaws", []).append(exact)

    updated["revision"] = int(current["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        backend.branch,
        "registry: bind NBA Spread Step3 exact thaw",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    exact_matches = [
        item for item in readback.get("active_thaws", [])
        if item.get("thaw_id") == THAW_ID
    ]
    if exact_matches != [exact]:
        raise NBAGroupStep3AuthorityFailure("NBA_STEP3_THAW_READBACK_MISMATCH")
    return readback, thaw_files


def _prepare_lease(client, candidate_sha: str, changed: tuple[str, ...], registry: dict, thaw_files: dict[str, dict[str, str]]):
    raw = client.content(LEASE_PATH, ref=LEASE_REF)
    state = validate_state(_decode_json(raw, "NBA_STEP3_SCOPE_LEASE"))
    working = state

    stale_ids = [
        str(holder["lease_id"])
        for holder in working.get("holders", [])
        if holder.get("owner_id") == OWNER_ID
    ]
    for lease_id in stale_ids:
        released = release_scope(
            working,
            owner_id=OWNER_ID,
            lease_id=lease_id,
            expected_revision=int(working["revision"]),
            expected_state_hash=str(working["state_hash"]),
        )
        if released["result"].get("allowed") is not True:
            raise NBAGroupStep3AuthorityFailure("NBA_STEP3_STALE_LEASE_RELEASE_FAILED")
        working = released["state"]

    scope = build_scope(
        write_paths=changed,
        dependency_tokens=("workstream:nba-spread-two-page-v1",),
        shared_resources=("surface:nba-spread-page1",),
        resource_identity={
            "candidate_sha": candidate_sha,
            "source_main_sha": SOURCE_MAIN_SHA,
            "registry_state_hash": str(registry["state_hash"]),
        },
    )
    claimed = claim_scope(
        working,
        owner_id=OWNER_ID,
        now_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        scope=scope,
        expected_revision=int(working["revision"]),
        expected_state_hash=str(working["state_hash"]),
        ttl_seconds=1800,
        frozen_paths=tuple(validate_registry(registry)["artifacts"].keys()),
        thawed_paths=tuple(thaw_files.keys()),
    )
    if claimed["result"].get("allowed") is not True:
        raise NBAGroupStep3AuthorityFailure(
            "NBA_STEP3_SCOPE_LEASE_BLOCKED:" + str(claimed["result"].get("decision"))
        )

    client.update_content(
        LEASE_PATH,
        json.dumps(claimed["state"], indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        LEASE_REF,
        "lease: bind NBA Spread Step3 exact scope",
        str(raw.get("sha") or ""),
    )
    readback = validate_state(
        _decode_json(client.content(LEASE_PATH, ref=LEASE_REF), "NBA_STEP3_SCOPE_LEASE_READBACK")
    )
    lease_id = str(claimed["result"]["lease_id"])
    if len([item for item in readback.get("holders", []) if item.get("lease_id") == lease_id]) != 1:
        raise NBAGroupStep3AuthorityFailure("NBA_STEP3_SCOPE_LEASE_READBACK_MISMATCH")
    return {
        "lease_id": lease_id,
        "lease_revision": int(readback["revision"]),
        "lease_state_hash": str(readback["state_hash"]),
        "released_prior_lease_ids": stale_ids,
    }


def execute(app):
    candidate_sha = _candidate()
    changed, main_tree, candidate_tree = _changed_paths(app.state.github_client, candidate_sha)
    registry, thaw_files = _prepare_registry(
        app.state.github_client,
        candidate_sha,
        changed,
        main_tree,
        candidate_tree,
    )
    lease = _prepare_lease(
        app.state.github_client,
        candidate_sha,
        changed,
        registry,
        thaw_files,
    )
    request = ProofRequest(
        task_id=TASK_ID,
        workstream=WORKSTREAM,
        candidate_sha=candidate_sha,
        lease_id=lease["lease_id"],
        authorization_id=AUTHORIZATION_ID,
        expected_main_sha=SOURCE_MAIN_SHA,
    )
    result = execute_proof_request(
        request,
        settings=app.state.settings,
        github_client=app.state.github_client,
        orchestrator=app.state.orchestrator,
        receipts=app.state.receipts,
    )
    return {
        **dict(result),
        "authority_status": "BOUND",
        "changed_paths": list(changed),
        "thaw_id": THAW_ID if thaw_files else None,
        "thawed_paths": sorted(thaw_files),
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
        **lease,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    @app.on_event("startup")
    def _run():
        if os.environ.pop(ENV_TRIGGER, "").strip() != "1":
            return
        try:
            result = execute(app)
        except Exception as exc:
            result = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:2000],
            }
        app.state.nba_spread_step3_authority_prove = result
        print(
            "NBA_SPREAD_STEP3_AUTHORITY_PROVE="
            + json.dumps(result, sort_keys=True, default=str),
            flush=True,
        )
    return app
