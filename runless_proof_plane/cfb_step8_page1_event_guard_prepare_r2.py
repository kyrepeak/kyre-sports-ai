from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import build_scope, claim_scope, release_scope, validate_state as validate_scope_state

from .models import ProofRequest
from .prove import execute_proof_request
from .registry import REGISTRY_PATH

MAIN_SHA = "c102a55985dbe2c3ab2ece3d24a7c82206989173"
CANDIDATE_SHA = "db8eabcfdb924384edffda0788ff72f23f1bbe81"
CANDIDATE_BRANCH = "cfb-step8-final-routing-fix-r2"
TASK_ID = "cfb-game-total-step8-page1-event-guard-r1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
AUTHORIZATION_ID = "AUTH-CFB-GT-STEP8-PAGE1-EVENT-GUARD-R2"
ROUTER = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
ROUTER_FROM = "811b0cec681aa1b1b0fddc4c3d4170dd3770dd50"
ROUTER_R1 = "2a73aba9b5a746a4e5ab8ab7040210df3e705666"
ROUTER_R2 = "f6ac3a2a79f8ff1fde6013b399d24d2ffb0ed744"
THAW_ID = "THAW-CFB-GT-STEP8-PAGE1-EVENT-GUARD-R1"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-page1-event-guard-r2"


class PrepareFailure(RuntimeError):
    pass


def _decode(raw):
    if not raw or raw.get("encoding") != "base64":
        raise PrepareFailure("CONTENT_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _text(payload):
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _claim(client, registry_hash: str):
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode(raw))
    if state.get("holders"):
        raise PrepareFailure("STEP2A_ACTIVE_HOLDER_BLOCK")
    scope = build_scope(
        write_paths=[ROUTER, "tests/test_cfb_game_total_step8_page1_event_guard_r1.py", REGISTRY_PATH],
        dependency_tokens=["cfb:game-total:step8", "router:cfb-game-total"],
        shared_resources=["ref:monster-frozen-artifact-registry", "route:cfb-game-total"],
        resource_identity={"main_sha": MAIN_SHA, "candidate_sha": CANDIDATE_SHA, "registry_state_hash": registry_hash},
        exclusive=False,
    )
    claimed = claim_scope(
        state,
        owner_id=OWNER,
        now_utc=_now(),
        scope=scope,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
        ttl_seconds=1200,
    )
    if claimed["result"].get("allowed") is not True:
        raise PrepareFailure("LEASE_BLOCKED:" + json.dumps(claimed["result"], sort_keys=True))
    client.update_content(LEASE_PATH, _text(claimed["state"]), LEASE_BRANCH, "lease: CFB Step8 real-tap repair", raw["sha"])
    return str(claimed["result"]["lease_id"])


def _release(client, lease_id: str):
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode(raw))
    holder = next((h for h in state.get("holders", []) if h.get("lease_id") == lease_id and h.get("owner_id") == OWNER), None)
    if not holder:
        return
    released = release_scope(
        state,
        owner_id=OWNER,
        lease_id=lease_id,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    if released["result"].get("allowed") is True:
        client.update_content(LEASE_PATH, _text(released["state"]), LEASE_BRANCH, "lease: release CFB Step8 real-tap repair", raw["sha"])


def _retarget_thaw(client):
    raw = client.content(REGISTRY_PATH, ref="monster-frozen-artifact-registry")
    registry = _decode(raw)
    validated = validate_registry(registry)
    if validated["artifacts"].get(ROUTER) != ROUTER_FROM:
        raise PrepareFailure("ROUTER_FROZEN_BASELINE_DRIFT")
    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if main_tree.get(ROUTER) != ROUTER_R1 or candidate_tree.get(ROUTER) != ROUTER_R2:
        raise PrepareFailure("ROUTER_BLOB_IDENTITY_DRIFT")
    matches = [g for g in registry.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    if len(matches) != 1:
        raise PrepareFailure("EVENT_GUARD_THAW_NOT_UNIQUE")
    current = matches[0]
    expected = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": "d265eb22cc2919a603c75534373393d8a6c5c9f5",
        "files": {ROUTER: {"from_blob": ROUTER_FROM, "to_blob": ROUTER_R1}},
    }
    if current != expected:
        raise PrepareFailure("EVENT_GUARD_THAW_DRIFT")
    updated = deepcopy(registry)
    replacement = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {ROUTER: {"from_blob": ROUTER_FROM, "to_blob": ROUTER_R2}},
    }
    updated["active_thaws"] = [replacement if g.get("thaw_id") == THAW_ID else g for g in updated.get("active_thaws", [])]
    updated["revision"] = int(updated.get("revision", 0)) + 1
    updated["state_hash"] = _hash(_payload_without_hash(updated))
    validate_registry(updated)
    client.update_content(REGISTRY_PATH, _text(updated), "monster-frozen-artifact-registry", "registry: retarget Step8 event guard to real-tap repair", raw["sha"])
    readback = _decode(client.content(REGISTRY_PATH, ref="monster-frozen-artifact-registry"))
    validate_registry(readback)
    if readback != updated:
        raise PrepareFailure("REGISTRY_READBACK_MISMATCH")
    return readback


def execute(app):
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA:
        raise PrepareFailure("MAIN_DRIFT")
    if client.branch_sha(CANDIDATE_BRANCH) != CANDIDATE_SHA:
        raise PrepareFailure("CANDIDATE_BRANCH_DRIFT")
    registry = _decode(client.content(REGISTRY_PATH, ref="monster-frozen-artifact-registry"))
    validate_registry(registry)
    lease_id = _claim(client, str(registry["state_hash"]))
    try:
        updated = _retarget_thaw(client)
        request = ProofRequest(
            task_id=TASK_ID,
            workstream=WORKSTREAM,
            candidate_sha=CANDIDATE_SHA,
            lease_id=lease_id,
            authorization_id=AUTHORIZATION_ID,
            expected_main_sha=MAIN_SHA,
        )
        proof = execute_proof_request(
            request,
            settings=app.state.settings,
            github_client=client,
            orchestrator=app.state.orchestrator,
            receipts=app.state.receipts,
        )
        return {
            "status": proof.get("status"),
            "candidate_sha": CANDIDATE_SHA,
            "lease_id": lease_id,
            "registry_revision": updated["revision"],
            "registry_state_hash": updated["state_hash"],
            "thaw_id": THAW_ID,
            "proof": proof,
            "github_actions_fallback": 0,
        }
    finally:
        _release(client, lease_id)


def install_startup(app):
    app.state.cfb_step8_page1_event_guard_prepare_r2 = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:12000]}
        app.state.cfb_step8_page1_event_guard_prepare_r2 = result
        print("CFB_STEP8_PAGE1_EVENT_GUARD_PREPARE_R2=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    return app
