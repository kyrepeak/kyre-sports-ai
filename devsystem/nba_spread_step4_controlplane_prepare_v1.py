"""Ephemeral Runless helper for NBA Spread Step 4 control-plane preparation.

Mutates only the authoritative frozen-registry thaw grant and scope-aware lease
required for the already-locked Step-4 product candidate. No product runtime or
GitHub Actions mutation is performed here.
"""
from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import _hash as registry_hash
from devsystem.frozen_artifact_registry_v1 import _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import build_scope, claim_scope, release_scope, validate_state
from runless_proof_plane.config import Settings
from runless_proof_plane.github_app import GithubAppAuth
from runless_proof_plane.github_client import GithubClient
from runless_proof_plane.registry import GithubRegistryBackend, REGISTRY_PATH

SOURCE_MAIN_SHA = "6b3a37891fc2938736e8f371d29c3337682a4a22"
CANDIDATE_SHA = "fd6d12a894ebb105ba9911647c4b8a60c5637d16"
STEP4_BRANCH = "nba-spread-step4-most-bet-r1"
THAW_ID = "THAW-NBA-SPREAD-STEP4-MOST-BET-R1"
OWNER_ID = "chatgpt:api2:nba-spread-step4-most-bet-v1"
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
ALLOWED_PATHS = {
    "devsystem/execution_plans/nba-spread-step4-most-bet-v1.json",
    "devsystem/runless_proof_plans/nba-spread-step4-most-bet-v1.json",
    "devsystem/task_ledgers/nba-spread-step4-most-bet-v1.json",
    "nba_spread_most_bet_v1.py",
    "nba_spread_page_v1.py",
    "tests/test_nba_spread_step4_most_bet_v1.py",
}


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise RuntimeError(label + "_DECODE_FAILED") from exc


def main() -> None:
    settings = Settings.from_env()
    if settings.bootstrap:
        raise RuntimeError("NBA_STEP4_PREP_REQUIRES_FULL_RUNLESS_AUTHORITY")
    client = GithubClient(GithubAppAuth(settings), settings.repository)

    if client.branch_sha("main") != SOURCE_MAIN_SHA:
        raise RuntimeError("NBA_STEP4_MAIN_DRIFT")
    if client.branch_sha(STEP4_BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("NBA_STEP4_BRANCH_HEAD_DRIFT")

    main_tree = client.tree_blobs(SOURCE_MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    changed = tuple(sorted(
        path for path in set(main_tree) | set(candidate_tree)
        if main_tree.get(path) != candidate_tree.get(path)
    ))
    unexpected = sorted(set(changed) - ALLOWED_PATHS)
    if unexpected or not changed:
        raise RuntimeError("NBA_STEP4_SCOPE_DRIFT:" + ",".join(unexpected))

    backend = GithubRegistryBackend(client)
    current = backend.read_registry()
    validated = validate_registry(current)
    if str(current.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        raise RuntimeError("NBA_STEP4_REGISTRY_MAIN_DRIFT")

    thaw_files: dict[str, dict[str, str]] = {}
    for path in changed:
        if path not in validated["artifacts"]:
            continue
        expected = str(validated["artifacts"][path])
        before = str(main_tree.get(path) or "")
        after = str(candidate_tree.get(path) or "")
        if before != expected:
            raise RuntimeError("NBA_STEP4_FROZEN_BASELINE_DRIFT:" + path)
        if not after:
            raise RuntimeError("NBA_STEP4_FROZEN_ARTIFACT_DELETED:" + path)
        thaw_files[path] = {"from_blob": expected, "to_blob": after}

    exact_thaw = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": deepcopy(thaw_files),
    }
    matches = [i for i, item in enumerate(current.get("active_thaws", [])) if item.get("thaw_id") == THAW_ID]
    if len(matches) > 1:
        raise RuntimeError("NBA_STEP4_DUPLICATE_THAW_ID")

    registry = current
    if thaw_files and not (matches and current["active_thaws"][matches[0]] == exact_thaw):
        updated = deepcopy(current)
        if matches:
            prior = updated["active_thaws"][matches[0]]
            if set(prior.get("files") or {}) != set(thaw_files):
                raise RuntimeError("NBA_STEP4_THAW_FILESET_DRIFT")
            updated["active_thaws"][matches[0]] = exact_thaw
        else:
            updated.setdefault("active_thaws", []).append(exact_thaw)
        updated["revision"] = int(current["revision"]) + 1
        updated.pop("state_hash", None)
        updated["state_hash"] = registry_hash(_payload_without_hash(updated))
        validate_registry(updated)
        client.update_content(
            REGISTRY_PATH,
            json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            backend.branch,
            "registry: bind NBA Spread Step4 exact thaw",
            backend._blob_sha,
        )
        registry = backend.read_registry()

    exact_matches = [item for item in registry.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if thaw_files and exact_matches != [exact_thaw]:
        raise RuntimeError("NBA_STEP4_THAW_READBACK_MISMATCH")

    raw = client.content(LEASE_PATH, ref=LEASE_REF)
    working = validate_state(_decode_json(raw, "NBA_STEP4_SCOPE_LEASE"))
    for holder in list(working.get("holders", [])):
        if holder.get("owner_id") != OWNER_ID:
            continue
        released = release_scope(
            working,
            owner_id=OWNER_ID,
            lease_id=str(holder["lease_id"]),
            expected_revision=int(working["revision"]),
            expected_state_hash=str(working["state_hash"]),
        )
        if released["result"].get("allowed") is not True:
            raise RuntimeError("NBA_STEP4_STALE_LEASE_RELEASE_FAILED")
        working = released["state"]

    scope = build_scope(
        write_paths=changed,
        dependency_tokens=("workstream:nba-spread-two-page-v1",),
        shared_resources=("surface:nba-spread-page1",),
        resource_identity={
            "candidate_sha": CANDIDATE_SHA,
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
        ttl_seconds=7200,
        frozen_paths=tuple(validate_registry(registry)["artifacts"].keys()),
        thawed_paths=tuple(thaw_files.keys()),
    )
    if claimed["result"].get("allowed") is not True:
        raise RuntimeError("NBA_STEP4_SCOPE_LEASE_BLOCKED:" + str(claimed["result"].get("decision")))

    client.update_content(
        LEASE_PATH,
        json.dumps(claimed["state"], indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        LEASE_REF,
        "lease: bind NBA Spread Step4 exact scope",
        str(raw.get("sha") or ""),
    )
    readback = validate_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_REF), "NBA_STEP4_SCOPE_LEASE_READBACK"))
    lease_id = str(claimed["result"]["lease_id"])
    if len([h for h in readback.get("holders", []) if h.get("lease_id") == lease_id]) != 1:
        raise RuntimeError("NBA_STEP4_SCOPE_LEASE_READBACK_MISMATCH")

    print(json.dumps({
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "changed_paths": list(changed),
        "thaw_id": THAW_ID,
        "thawed_paths": sorted(thaw_files),
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
        "lease_id": lease_id,
        "lease_revision": int(readback["revision"]),
        "lease_state_hash": str(readback["state_hash"]),
        "github_actions_fallback": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
