from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone
from threading import Thread

from devsystem.frozen_artifact_registry_v1 import _hash as registry_hash
from devsystem.frozen_artifact_registry_v1 import _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    release_scope,
    validate_state as validate_scope_state,
)

from .models import ProofRequest
from .prove import execute_proof_request

MAIN_SHA = "f1f0ccd80ea717623f38be49237e4943e9d43ad6"
CANDIDATE_SHA = "892798332abfd1b696a9e4809d51861302c6c3b3"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
TASK_ID = "cfb-game-total-step8-route-pointer-lock-r1"
AUTHORIZATION_ID = "AUTH-CFB-GT-STEP8-ROUTE-POINTER-LOCK-R1"
OWNER_ID = "api2/cfb-game-total-native-website-rebuild-v1/step8-route-pointer-lock-r1"

REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"

ROUTER_PATH = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
TEST_PATH = "tests/test_cfb_game_total_step8_route_pointer_lock_r1.py"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-step8-route-pointer-lock-r1.json"
FROM_BLOB = "f6ac3a2a79f8ff1fde6013b399d24d2ffb0ed744"
TO_BLOB = "23e63bb1d87a9081a0b969f92922e5d5da7e9358"
THAW_ID = "THAW-CFB-GT-STEP8-ROUTE-POINTER-LOCK-R1"


class RoutePointerPremergeFailure(RuntimeError):
    pass


def _decode(raw):
    if not raw or raw.get("encoding") != "base64":
        raise RoutePointerPremergeFailure("CONTENT_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _text(payload):
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ensure_candidate(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RoutePointerPremergeFailure("MAIN_DRIFT")
    commit = client.commit(CANDIDATE_SHA)
    if str(commit.get("sha") or "") != CANDIDATE_SHA:
        raise RoutePointerPremergeFailure("CANDIDATE_DRIFT")
    tree = client.tree_blobs(CANDIDATE_SHA)
    if tree.get(ROUTER_PATH) != TO_BLOB:
        raise RoutePointerPremergeFailure("ROUTER_BLOB_DRIFT")
    for path in (TEST_PATH, PLAN_PATH):
        if not tree.get(path):
            raise RoutePointerPremergeFailure("CANDIDATE_ARTIFACT_MISSING:" + path)


def _ensure_thaw(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    reg = _decode(raw)
    checked = validate_registry(reg)
    if str(reg.get("source_main_sha") or "") != MAIN_SHA:
        raise RoutePointerPremergeFailure(
            "REGISTRY_MAIN_DRIFT:" + str(reg.get("source_main_sha") or "")
        )

    expected = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {ROUTER_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }
    same_id = [x for x in reg.get("active_thaws", []) if x.get("thaw_id") == THAW_ID]
    if same_id:
        if len(same_id) != 1 or same_id[0] != expected:
            raise RoutePointerPremergeFailure("THAW_IDENTITY_DRIFT")
        return {
            "revision": int(reg["revision"]),
            "state_hash": str(reg["state_hash"]),
            "reused": True,
        }

    duplicates = [
        x for x in reg.get("active_thaws", [])
        if x.get("target_head_sha") == CANDIDATE_SHA and ROUTER_PATH in (x.get("files") or {})
    ]
    if duplicates:
        raise RoutePointerPremergeFailure("DUPLICATE_EXACT_HEAD_THAW")

    updated = deepcopy(reg)
    updated["active_thaws"].append(expected)
    updated["active_thaws"] = sorted(updated["active_thaws"], key=lambda x: str(x.get("thaw_id") or ""))
    updated["revision"] = int(updated["revision"]) + 1
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        _text(updated),
        REGISTRY_BRANCH,
        "registry: thaw CFB Step8 route-pointer lock candidate",
        raw["sha"],
    )
    rb = _decode(client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH))
    validate_registry(rb)
    match = [x for x in rb.get("active_thaws", []) if x.get("thaw_id") == THAW_ID]
    if len(match) != 1 or match[0] != expected:
        raise RoutePointerPremergeFailure("THAW_READBACK_FAILED")
    return {
        "revision": int(rb["revision"]),
        "state_hash": str(rb["state_hash"]),
        "reused": False,
    }


def _claim(client, reg_state_hash):
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode(raw))
    owned = [h for h in state.get("holders", []) if h.get("owner_id") == OWNER_ID]
    if owned:
        if len(owned) != 1:
            raise RoutePointerPremergeFailure("LEASE_OWNER_NOT_UNIQUE")
        holder = owned[0]
        if holder.get("scope", {}).get("resource_identity", {}).get("main_sha") != MAIN_SHA:
            raise RoutePointerPremergeFailure("LEASE_MAIN_DRIFT")
        return str(holder["lease_id"])

    scope = build_scope(
        write_paths=[ROUTER_PATH, TEST_PATH, PLAN_PATH],
        dependency_tokens=[f"candidate:{CANDIDATE_SHA}", "cfb:game-total:step8"],
        shared_resources=[
            "ref:monster-frozen-artifact-registry",
            "ref:runless-proof-receipts",
            "route:cfb-game-total",
            "runless-proof-plane",
        ],
        resource_identity={
            "main_sha": MAIN_SHA,
            "registry_state_hash": reg_state_hash,
        },
        exclusive=False,
    )
    claimed = claim_scope(
        state,
        owner_id=OWNER_ID,
        now_utc=_now(),
        scope=scope,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
        ttl_seconds=1800,
        frozen_paths=[ROUTER_PATH],
        thawed_paths=[ROUTER_PATH],
    )
    if claimed["result"].get("allowed") is not True:
        raise RoutePointerPremergeFailure("LEASE_BLOCKED:" + json.dumps(claimed["result"], sort_keys=True))
    client.update_content(
        LEASE_PATH,
        _text(claimed["state"]),
        LEASE_BRANCH,
        "lease: claim CFB Step8 route-pointer lock premerge",
        raw["sha"],
    )
    lease_id = str(claimed["result"]["lease_id"])
    rb = validate_scope_state(_decode(client.content(LEASE_PATH, ref=LEASE_BRANCH)))
    if len([h for h in rb.get("holders", []) if h.get("lease_id") == lease_id]) != 1:
        raise RoutePointerPremergeFailure("LEASE_READBACK_FAILED")
    return lease_id


def _release(client, lease_id):
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode(raw))
    if not any(h.get("lease_id") == lease_id for h in state.get("holders", [])):
        return
    released = release_scope(
        state,
        owner_id=OWNER_ID,
        lease_id=lease_id,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    if released["result"].get("allowed") is not True:
        raise RoutePointerPremergeFailure("LEASE_RELEASE_FAILED")
    client.update_content(
        LEASE_PATH,
        _text(released["state"]),
        LEASE_BRANCH,
        "lease: release failed CFB Step8 route-pointer lock premerge",
        raw["sha"],
    )


def execute(app):
    client = app.state.github_client
    _ensure_candidate(client)
    thaw = _ensure_thaw(client)
    lease_id = _claim(client, thaw["state_hash"])
    request = ProofRequest(
        task_id=TASK_ID,
        workstream=WORKSTREAM,
        candidate_sha=CANDIDATE_SHA,
        lease_id=lease_id,
        authorization_id=AUTHORIZATION_ID,
        expected_main_sha=MAIN_SHA,
    )
    result = execute_proof_request(
        request,
        settings=app.state.settings,
        github_client=client,
        orchestrator=app.state.orchestrator,
        receipts=app.state.receipts,
    )
    if result.get("status") != "MERGE_AUTHORIZED":
        _release(client, lease_id)
        raise RoutePointerPremergeFailure("RUNLESS_PREMERGE_FAILED:" + json.dumps(result, sort_keys=True, default=str))
    return {
        "status": "MERGE_AUTHORIZED",
        "candidate_sha": CANDIDATE_SHA,
        "task_id": TASK_ID,
        "workstream": WORKSTREAM,
        "lease_id": lease_id,
        "thaw_id": THAW_ID,
        "registry_revision": thaw["revision"],
        "registry_state_hash": thaw["state_hash"],
        "proof_id": result.get("proof_id"),
        "receipt_digest": result.get("receipt_digest"),
        "github_actions_fallback": 0,
        "duplicate_proof_runs": 0,
    }


def install_startup(app):
    app.state.cfb_step8_route_pointer_lock_premerge_r1 = {"status": "STARTING"}

    def worker():
        try:
            result = execute(app)
        except Exception as exc:
            result = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:32000],
                "github_actions_fallback": 0,
                "duplicate_proof_runs": 0,
            }
        app.state.cfb_step8_route_pointer_lock_premerge_r1 = result
        print(
            "CFB_STEP8_ROUTE_POINTER_LOCK_PREMERGE_R1="
            + json.dumps(result, sort_keys=True, default=str),
            flush=True,
        )

    @app.on_event("startup")
    def run():
        Thread(target=worker, name="cfb-step8-route-pointer-lock-premerge-r1", daemon=True).start()

    return app
