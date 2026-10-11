from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import build_scope, claim_scope, release_scope, validate_state as validate_scope_state
from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port

from .models import ProofRequest
from .prove import execute_proof_request
from .registry import REGISTRY_PATH

MAIN_SHA = "e6490b5e52a32c16b283cd676fb0c51c02e2b7df"
RECOVERY_HEAD = "b8a693bdce3f0e17a602e67fe89a60f63457b15a"
CANDIDATE_SHA = "d265eb22cc2919a603c75534373393d8a6c5c9f5"
CANDIDATE_BRANCH = "cfb-step8-page1-event-guard-r1"
TASK_ID = "cfb-game-total-step8-page1-event-guard-r1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
AUTHORIZATION_ID = "AUTH-CFB-GT-STEP8-PAGE1-EVENT-GUARD-R1"
ROUTER = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
ROUTER_FROM = "811b0cec681aa1b1b0fddc4c3d4170dd3770dd50"
ROUTER_TO = "2a73aba9b5a746a4e5ab8ab7040210df3e705666"
THAW_ID = "THAW-CFB-GT-STEP8-PAGE1-EVENT-GUARD-R1"
REQUIREMENTS = "requirements.txt"
REQUIREMENTS_FROM = "1022d95a71b3c04aa5310b5057de74978e4cffa4"
REQUIREMENTS_TO = "7b2e379fc2f519c9bb8700a14b33b70d4eb0f581"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
OLD_LEASE_ID = "SCOPE-LEASE-6E91B4C27A53D8F0B21C44E7"
OLD_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-deploy-refresh-proof-r2"
OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-page1-event-guard-r1"


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


def _lease(client, registry_hash):
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode(raw))
    working = state
    old = next((h for h in working.get("holders", []) if h.get("lease_id") == OLD_LEASE_ID and h.get("owner_id") == OLD_OWNER), None)
    if old:
        released = release_scope(
            working,
            owner_id=OLD_OWNER,
            lease_id=OLD_LEASE_ID,
            expected_revision=working["revision"],
            expected_state_hash=working["state_hash"],
        )
        if released["result"].get("allowed") is not True:
            raise PrepareFailure("OLD_LEASE_RELEASE_FAILED")
        working = released["state"]
    scope = build_scope(
        write_paths=[ROUTER, "tests/test_cfb_game_total_step8_page1_event_guard_r1.py", "devsystem/runless_proof_plans/cfb-game-total-step8-page1-event-guard-r1.json", REGISTRY_PATH],
        dependency_tokens=["cfb:game-total:step8", "router:cfb-game-total"],
        shared_resources=["ref:monster-frozen-artifact-registry", "route:cfb-game-total"],
        resource_identity={"main_sha": MAIN_SHA, "candidate_sha": CANDIDATE_SHA, "registry_state_hash": registry_hash},
        exclusive=False,
    )
    claimed = claim_scope(
        working,
        owner_id=OWNER,
        now_utc=_now(),
        scope=scope,
        expected_revision=working["revision"],
        expected_state_hash=working["state_hash"],
        ttl_seconds=1800,
    )
    if claimed["result"].get("allowed") is not True:
        raise PrepareFailure("REPAIR_LEASE_BLOCKED:" + json.dumps(claimed["result"], sort_keys=True))
    client.update_content(LEASE_PATH, _text(claimed["state"]), LEASE_BRANCH, "lease: handoff CFB Step8 to page1 event guard", raw["sha"])
    return str(claimed["result"]["lease_id"])


def _reconcile_and_thaw(client):
    raw = client.content(REGISTRY_PATH, ref="monster-frozen-artifact-registry")
    registry = _decode(raw)
    validated = validate_registry(registry)
    if str(registry.get("source_main_sha") or "") != "1b0169a8a6e644ae6971685fb50b9bd96d510106":
        raise PrepareFailure("REGISTRY_SOURCE_MAIN_DRIFT")
    if validated["artifacts"].get(REQUIREMENTS) != REQUIREMENTS_FROM:
        raise PrepareFailure("REQUIREMENTS_BASELINE_DRIFT")
    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if main_tree.get(REQUIREMENTS) != REQUIREMENTS_TO:
        raise PrepareFailure("MAIN_REQUIREMENTS_BLOB_DRIFT")
    if main_tree.get(ROUTER) != ROUTER_FROM or candidate_tree.get(ROUTER) != ROUTER_TO:
        raise PrepareFailure("ROUTER_BLOB_IDENTITY_DRIFT")
    recovery = client.commit(RECOVERY_HEAD)
    if not recovery or client.branch_sha("main") != MAIN_SHA:
        raise PrepareFailure("MAIN_OR_RECOVERY_IDENTITY_DRIFT")

    planned = plan_baseline_forward_port(
        registry,
        updates={REQUIREMENTS: {"from_blob": REQUIREMENTS_FROM, "to_blob": REQUIREMENTS_TO}},
        source_main_sha=MAIN_SHA,
    )
    next_registry = deepcopy(planned["registry"])
    if "THAW-CFB-GT-STEP8-STREAMLIT-REDEPLOY-R1" not in set(planned.get("retired_empty_thaw_grants") or []):
        raise PrepareFailure("REDEPLOY_THAW_NOT_RETIRED")
    existing = [g for g in next_registry.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    exact = {"thaw_id": THAW_ID, "status": "ACTIVE", "target_head_sha": CANDIDATE_SHA, "files": {ROUTER: {"from_blob": ROUTER_FROM, "to_blob": ROUTER_TO}}}
    if existing:
        if len(existing) != 1 or existing[0] != exact:
            raise PrepareFailure("EVENT_GUARD_THAW_DRIFT")
    else:
        next_registry["active_thaws"].append(exact)
        next_registry["active_thaws"] = sorted(next_registry["active_thaws"], key=lambda row: str(row.get("thaw_id") or ""))
    next_registry["state_hash"] = _hash(_payload_without_hash(next_registry))
    validate_registry(next_registry)
    client.update_content(REGISTRY_PATH, _text(next_registry), "monster-frozen-artifact-registry", "registry: reconcile Step8 deploy and authorize page1 event guard", raw["sha"])
    readback = _decode(client.content(REGISTRY_PATH, ref="monster-frozen-artifact-registry"))
    validate_registry(readback)
    if readback != next_registry:
        raise PrepareFailure("REGISTRY_READBACK_MISMATCH")
    return readback


def execute(app):
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA:
        raise PrepareFailure("MAIN_DRIFT")
    registry = _decode(client.content(REGISTRY_PATH, ref="monster-frozen-artifact-registry"))
    validate_registry(registry)
    lease_id = _lease(client, str(registry["state_hash"]))
    reconciled = _reconcile_and_thaw(client)
    ref = client.get_ref(CANDIDATE_BRANCH)
    if ref is None:
        client.create_ref(CANDIDATE_BRANCH, CANDIDATE_SHA)
    elif str((ref.get("object") or {}).get("sha") or "") != CANDIDATE_SHA:
        raise PrepareFailure("CANDIDATE_BRANCH_DRIFT")
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
        "registry_revision": reconciled["revision"],
        "registry_state_hash": reconciled["state_hash"],
        "thaw_id": THAW_ID,
        "proof": proof,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_step8_page1_event_guard_prepare = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:12000]}
        app.state.cfb_step8_page1_event_guard_prepare = result
        print("CFB_STEP8_PAGE1_EVENT_GUARD_PREPARE=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    return app
