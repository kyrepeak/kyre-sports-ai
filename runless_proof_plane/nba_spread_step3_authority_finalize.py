from __future__ import annotations

import base64
import json
from copy import deepcopy

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import release_scope, validate_state

REPOSITORY = "kyrepeak/kyre-sports-ai"
MAIN_SHA = "6b3a37891fc2938736e8f371d29c3337682a4a22"
SOURCE_MAIN_SHA = "30e803ea943091d07e760d9d4e003e110cbc29ed"
CANDIDATE_SHA = "196295abd07610b47af30ae8542683f0143b6b25"

REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
INITIAL_REGISTRY_REVISION = 295
INITIAL_REGISTRY_HASH = "0389b304ab6cd1fe955d331de90671680ebbb3369297db66ccbef1faa678d6bc"
FREEZE_TOKEN = "NBA_SPREAD_STEP3_SCHEDULE_PHOENIX_FROZEN"
THAW_ID = "THAW-NBA-SPREAD-STEP3-SCHEDULE-PHOENIX-R1"
PAGE_PATH = "nba_spread_page_v1.py"
PAGE_OLD_BLOB = "8becdc6be21e8956e8f8101ebb3a930897f61cf6"
PAGE_NEW_BLOB = "b55cfb431dcbb867b5bfd5807efeca1dc66ebcb0"
ARTIFACTS = (
    "devsystem/execution_plans/nba-spread-step3-schedule-phoenix-v1.json",
    "devsystem/runless_proof_plans/nba-spread-step3-schedule-phoenix-v1.json",
    "devsystem/task_ledgers/nba-spread-step3-schedule-phoenix-v1.json",
    "nba_spread_page_v1.py",
    "nba_spread_schedule_v1.py",
    "tests/test_nba_spread_step3_schedule_phoenix_v1.py",
)

LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
INITIAL_LEASE_REVISION = 665
INITIAL_LEASE_HASH = "21c11510c223b4f5ce69a0c43485a9be128dbaaf8e6e93030e353b6af2b08852"
LEASES = (
    (
        "chatgpt:api2:nba-spread-step3-controlplane-prep-v1",
        "SCOPE-LEASE-AB2D48AD5187944024E5F8C2",
        "b7e1a0cd9fc912a609b22710e1d5a6bc69e95955",
    ),
    (
        "chatgpt:api2:nba-spread-step3-schedule-phoenix-v1",
        "SCOPE-LEASE-D93F7CC6EEB68AB8A8F1B0E9",
        CANDIDATE_SHA,
    ),
)


def _decode(meta: dict) -> dict:
    return json.loads(base64.b64decode(str(meta["content"]).replace("\n", "")).decode("utf-8"))


def _encode(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _artifact_blobs(client) -> dict[str, str]:
    blobs = client.tree_blobs(MAIN_SHA)
    result: dict[str, str] = {}
    for path in ARTIFACTS:
        blob = blobs.get(path)
        if not blob:
            raise RuntimeError(f"NBA_SPREAD_STEP3_FINALIZE_ARTIFACT_MISSING:{path}")
        result[path] = str(blob)
    if result[PAGE_PATH] != PAGE_NEW_BLOB:
        raise RuntimeError(f"NBA_SPREAD_STEP3_FINALIZE_PAGE_BLOB_DRIFT:{result[PAGE_PATH]}")
    return dict(sorted(result.items()))


def _verify_main(client) -> None:
    observed = client.branch_sha("main")
    if observed != MAIN_SHA:
        raise RuntimeError(f"NBA_SPREAD_STEP3_FINALIZE_MAIN_DRIFT:{observed}")
    comparison = client.request("GET", f"/compare/{CANDIDATE_SHA}...{MAIN_SHA}")
    merge_base = str((comparison.get("merge_base_commit") or {}).get("sha") or "")
    if merge_base != CANDIDATE_SHA:
        raise RuntimeError(f"NBA_SPREAD_STEP3_FINALIZE_CANDIDATE_NOT_ANCESTOR:{merge_base}")


def _finalize_registry(client, artifact_blobs: dict[str, str]) -> dict:
    meta = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    registry = _decode(meta)
    validate_registry(registry)

    existing = registry["entries"].get(FREEZE_TOKEN)
    if existing is None:
        if int(registry["revision"]) != INITIAL_REGISTRY_REVISION:
            raise RuntimeError(f"NBA_SPREAD_STEP3_FINALIZE_REGISTRY_REV_DRIFT:{registry['revision']}")
        if str(registry["state_hash"]) != INITIAL_REGISTRY_HASH:
            raise RuntimeError(f"NBA_SPREAD_STEP3_FINALIZE_REGISTRY_HASH_DRIFT:{registry['state_hash']}")
        if str(registry["source_main_sha"]) != SOURCE_MAIN_SHA:
            raise RuntimeError(f"NBA_SPREAD_STEP3_FINALIZE_REGISTRY_SOURCE_DRIFT:{registry['source_main_sha']}")

        grants = [g for g in registry["active_thaws"] if g.get("thaw_id") == THAW_ID]
        if len(grants) != 1:
            raise RuntimeError(f"NBA_SPREAD_STEP3_FINALIZE_THAW_COUNT:{len(grants)}")
        grant = grants[0]
        if grant.get("target_head_sha") != CANDIDATE_SHA:
            raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_THAW_TARGET_DRIFT")
        pair = (grant.get("files") or {}).get(PAGE_PATH) or {}
        if pair.get("from_blob") != PAGE_OLD_BLOB or pair.get("to_blob") != PAGE_NEW_BLOB:
            raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_THAW_PAIR_DRIFT")

        unrelated_thaws = deepcopy([g for g in registry["active_thaws"] if g.get("thaw_id") != THAW_ID])
        planned = plan_baseline_forward_port(
            registry,
            updates={PAGE_PATH: {"from_blob": PAGE_OLD_BLOB, "to_blob": PAGE_NEW_BLOB}},
            source_main_sha=MAIN_SHA,
        )
        next_registry = planned["registry"]
        if THAW_ID not in planned["retired_empty_thaw_grants"]:
            raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_THAW_NOT_RETIRED")
        if next_registry["active_thaws"] != unrelated_thaws:
            raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_UNRELATED_THAW_DRIFT")
        if int(next_registry["revision"]) != INITIAL_REGISTRY_REVISION + 1:
            raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_REGISTRY_REVISION_NOT_SINGLE_STEP")

        next_registry["entries"][FREEZE_TOKEN] = {
            "status": "FROZEN",
            "checkpoint_id": FREEZE_TOKEN,
            "source_main_sha": MAIN_SHA,
            "artifacts": artifact_blobs,
        }
        next_registry["state_hash"] = _hash(_payload_without_hash(next_registry))
        validate_registry(next_registry)
        client.update_content(
            REGISTRY_PATH,
            _encode(next_registry),
            REGISTRY_BRANCH,
            "NBA Spread Step 3 — transactional frozen registry closeout",
            meta["sha"],
        )

    read_meta = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    readback = _decode(read_meta)
    validate_registry(readback)
    entry = readback["entries"].get(FREEZE_TOKEN)
    if not entry or entry.get("status") != "FROZEN":
        raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_FREEZE_READBACK_MISSING")
    if entry.get("source_main_sha") != MAIN_SHA:
        raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_FREEZE_SOURCE_DRIFT")
    if dict(sorted((entry.get("artifacts") or {}).items())) != artifact_blobs:
        raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_FREEZE_ARTIFACT_DRIFT")
    if str(readback["source_main_sha"]) != MAIN_SHA:
        raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_REGISTRY_MAIN_READBACK_DRIFT")
    if int(readback["revision"]) != INITIAL_REGISTRY_REVISION + 1:
        raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_REGISTRY_REV_READBACK_DRIFT")
    if any(g.get("thaw_id") == THAW_ID for g in readback["active_thaws"]):
        raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_THAW_STILL_ACTIVE")
    return readback


def _finalize_leases(client) -> dict:
    meta = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_state(_decode(meta))
    holder_map = {h["lease_id"]: h for h in state["holders"]}
    target_ids = {lease_id for _, lease_id, _ in LEASES}

    targets_present = [lease_id for _, lease_id, _ in LEASES if lease_id in holder_map]
    if targets_present:
        if int(state["revision"]) != INITIAL_LEASE_REVISION or str(state["state_hash"]) != INITIAL_LEASE_HASH:
            raise RuntimeError(f"NBA_SPREAD_STEP3_FINALIZE_LEASE_STATE_DRIFT:{state['revision']}:{state['state_hash']}")
        if set(holder_map) != target_ids:
            raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_UNRELATED_LEASE_HOLDER_PRESENT")
        for owner, lease_id, candidate in LEASES:
            holder = holder_map.get(lease_id)
            if holder is None or holder.get("owner_id") != owner:
                raise RuntimeError(f"NBA_SPREAD_STEP3_FINALIZE_LEASE_IDENTITY_DRIFT:{lease_id}")
            identity = (holder.get("scope") or {}).get("resource_identity") or {}
            if identity.get("candidate_sha") != candidate:
                raise RuntimeError(f"NBA_SPREAD_STEP3_FINALIZE_LEASE_CANDIDATE_DRIFT:{lease_id}")

        next_state = state
        released: list[str] = []
        for owner, lease_id, _ in LEASES:
            result = release_scope(
                next_state,
                owner_id=owner,
                lease_id=lease_id,
                expected_revision=next_state["revision"],
                expected_state_hash=next_state["state_hash"],
            )
            if result["result"].get("allowed") is not True:
                raise RuntimeError(f"NBA_SPREAD_STEP3_FINALIZE_LEASE_RELEASE_BLOCKED:{lease_id}")
            next_state = result["state"]
            released.append(lease_id)
        if next_state["holders"]:
            raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_LEASE_RELEASE_LEFT_HOLDERS")
        client.update_content(
            LEASE_PATH,
            _encode(next_state),
            LEASE_BRANCH,
            "NBA Spread Step 3 — release finalization leases",
            meta["sha"],
        )

    read_meta = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    readback = validate_state(_decode(read_meta))
    if any(h["lease_id"] in target_ids for h in readback["holders"]):
        raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_LEASE_READBACK_STILL_HELD")
    if readback["holders"]:
        raise RuntimeError("NBA_SPREAD_STEP3_FINALIZE_UNRELATED_LEASE_READBACK_DRIFT")
    return readback


def finalize(client) -> dict:
    _verify_main(client)
    artifact_blobs = _artifact_blobs(client)
    registry = _finalize_registry(client, artifact_blobs)
    leases = _finalize_leases(client)
    return {
        "status": "GREEN",
        "decision": "NBA_SPREAD_STEP3_GREEN_FROZEN",
        "main_sha": MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "freeze_token": FREEZE_TOKEN,
        "frozen_artifact_count": len(artifact_blobs),
        "registry_revision": registry["revision"],
        "registry_state_hash": registry["state_hash"],
        "registry_source_main_sha": registry["source_main_sha"],
        "step3_thaw_active": False,
        "lease_revision": leases["revision"],
        "lease_state_hash": leases["state_hash"],
        "remaining_holder_count": len(leases["holders"]),
        "actions_fallback": 0,
    }


def finalize_from_env(client) -> dict:
    return finalize(client)
