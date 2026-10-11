from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone
from threading import Thread

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import validate_registry
from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    release_scope,
    validate_state as validate_scope_state,
)

from .models import ProofRequest
from .prove import execute_proof_request
from .registry import REGISTRY_PATH

MAIN_SHA = "283151c3792a73520a37b54bb8f480910004b6d6"
CANDIDATE_SHA = "d963f41bb7f13a0744a091249237ad95bc1cfc62"
TASK_ID = "cfb-game-total-step8-v14-source-event-guard-r1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
AUTHORIZATION_ID = "AUTH-CFB-GT-STEP8-V14-SOURCE-EVENT-GUARD-R1"
OWNER_ID = "api2/cfb-game-total-native-website-rebuild-v1/step8-v14-source-event-guard-r1"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
ROUTER = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
ROUTER_FROM = "2a73aba9b5a746a4e5ab8ab7040210df3e705666"
ROUTER_TO = "f6ac3a2a79f8ff1fde6013b399d24d2ffb0ed744"
THAW_ID = "THAW-CFB-GT-STEP8-PAGE1-EVENT-GUARD-R2"


class SubmitFailure(RuntimeError):
    pass


def _decode(raw):
    if not raw or raw.get("encoding") != "base64":
        raise SubmitFailure("CONTENT_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _text(payload):
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _gate_already_green(client) -> bool:
    combined = client.request("GET", f"/commits/{CANDIDATE_SHA}/status") or {}
    for status in combined.get("statuses", []):
        if status.get("context") == "runless-final-gate" and status.get("state") == "success":
            return True
    return False


def _claim(client):
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode(raw))
    scope = build_scope(
        write_paths=[REGISTRY_PATH, "devsystem/runless_proof_receipts"],
        dependency_tokens=[
            "cfb:game-total:step8",
            f"candidate:{CANDIDATE_SHA}",
            f"main:{MAIN_SHA}",
        ],
        shared_resources=[
            "ref:monster-frozen-artifact-registry",
            "route:cfb-game-total",
            "runless-proof-plane",
        ],
        resource_identity={
            "candidate_sha": CANDIDATE_SHA,
            "main_sha": MAIN_SHA,
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
    )
    if claimed["result"].get("allowed") is not True:
        raise SubmitFailure("STEP2A_LEASE_BLOCKED:" + json.dumps(claimed["result"], sort_keys=True))
    client.update_content(
        LEASE_PATH,
        _text(claimed["state"]),
        LEASE_BRANCH,
        "lease: claim CFB Step8 V14 exact-head Runless proof",
        raw["sha"],
    )
    return str(claimed["result"]["lease_id"])


def _release(client, lease_id: str):
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode(raw))
    holder = next(
        (
            item
            for item in state.get("holders", [])
            if item.get("owner_id") == OWNER_ID and item.get("lease_id") == lease_id
        ),
        None,
    )
    if not holder:
        return {"status": "ALREADY_RELEASED"}
    released = release_scope(
        state,
        owner_id=OWNER_ID,
        lease_id=lease_id,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    if released["result"].get("allowed") is not True:
        raise SubmitFailure("LEASE_RELEASE_FAILED:" + json.dumps(released["result"], sort_keys=True))
    client.update_content(
        LEASE_PATH,
        _text(released["state"]),
        LEASE_BRANCH,
        "lease: release CFB Step8 V14 exact-head Runless proof",
        raw["sha"],
    )
    check = validate_scope_state(_decode(client.content(LEASE_PATH, ref=LEASE_BRANCH)))
    if any(item.get("lease_id") == lease_id for item in check.get("holders", [])):
        raise SubmitFailure("LEASE_RELEASE_READBACK_FAILED")
    return {"status": "RELEASED", "revision": check["revision"], "state_hash": check["state_hash"]}


def _reconcile_registry(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    registry = _decode(raw)
    validated = validate_registry(registry)
    main_tree = client.tree_blobs(MAIN_SHA)
    if main_tree.get(ROUTER) != ROUTER_TO:
        raise SubmitFailure("MAIN_ROUTER_BLOB_DRIFT")

    active = list(registry.get("active_thaws", []))
    exact = [grant for grant in active if grant.get("thaw_id") == THAW_ID]
    if registry.get("source_main_sha") == MAIN_SHA and not exact:
        if validated["artifacts"].get(ROUTER) != ROUTER_TO:
            raise SubmitFailure("ALIGNED_REGISTRY_ROUTER_DRIFT")
        return {
            "status": "ALREADY_ALIGNED",
            "revision": registry["revision"],
            "state_hash": registry["state_hash"],
            "source_main_sha": registry["source_main_sha"],
        }

    if validated["artifacts"].get(ROUTER) != ROUTER_FROM:
        raise SubmitFailure("ROUTER_FROZEN_BASELINE_DRIFT")
    if len(exact) != 1:
        raise SubmitFailure("STEP8_ROUTER_THAW_NOT_UNIQUE")
    grant = exact[0]
    if grant.get("target_head_sha") != "1e6e4f51a8dc9a5cf0efca3b893ed4321eb9785a":
        raise SubmitFailure("STEP8_ROUTER_THAW_TARGET_DRIFT")
    pair = (grant.get("files") or {}).get(ROUTER) or {}
    if pair.get("from_blob") != ROUTER_FROM or pair.get("to_blob") != ROUTER_TO:
        raise SubmitFailure("STEP8_ROUTER_THAW_PAIR_DRIFT")

    before_unrelated = sorted(
        grant_item.get("thaw_id")
        for grant_item in active
        if grant_item.get("thaw_id") != THAW_ID
    )
    planned = plan_baseline_forward_port(
        registry,
        updates={ROUTER: {"from_blob": ROUTER_FROM, "to_blob": ROUTER_TO}},
        source_main_sha=MAIN_SHA,
    )
    if THAW_ID not in set(planned.get("retired_empty_thaw_grants") or []):
        raise SubmitFailure("STEP8_ROUTER_THAW_NOT_RETIRED")
    updated = deepcopy(planned["registry"])
    after_unrelated = sorted(item.get("thaw_id") for item in updated.get("active_thaws", []))
    if after_unrelated != before_unrelated:
        raise SubmitFailure("UNRELATED_THAW_DRIFT")
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        _text(updated),
        REGISTRY_BRANCH,
        "registry: reconcile merged CFB Step8 router thaw before V14 proof",
        raw["sha"],
    )
    readback = _decode(client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH))
    checked = validate_registry(readback)
    if (
        readback.get("source_main_sha") != MAIN_SHA
        or checked["artifacts"].get(ROUTER) != ROUTER_TO
        or any(item.get("thaw_id") == THAW_ID for item in readback.get("active_thaws", []))
        or sorted(item.get("thaw_id") for item in readback.get("active_thaws", [])) != before_unrelated
    ):
        raise SubmitFailure("REGISTRY_RECONCILIATION_READBACK_FAILED")
    return {
        "status": "RECONCILED",
        "revision": readback["revision"],
        "state_hash": readback["state_hash"],
        "source_main_sha": readback["source_main_sha"],
        "retired_thaw": THAW_ID,
        "preserved_thaws": before_unrelated,
    }


def execute(app):
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA:
        raise SubmitFailure("MAIN_DRIFT")
    if str(client.commit(CANDIDATE_SHA).get("sha") or "") != CANDIDATE_SHA:
        raise SubmitFailure("CANDIDATE_DRIFT")
    if _gate_already_green(client):
        return {
            "status": "ALREADY_MERGE_AUTHORIZED",
            "candidate_sha": CANDIDATE_SHA,
            "github_actions_fallback": 0,
        }

    lease_id = _claim(client)
    try:
        registry = _reconcile_registry(client)
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
            "registry": registry,
            "proof": proof,
            "github_actions_fallback": 0,
        }
    finally:
        release = _release(client, lease_id)
        print("CFB_STEP8_V14_SOURCE_GUARD_LEASE_RELEASE=" + json.dumps(release, sort_keys=True), flush=True)


def install_startup(app):
    app.state.cfb_step8_v14_source_guard_submit = {"status": "STARTING"}

    def _worker():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:16000]}
        app.state.cfb_step8_v14_source_guard_submit = result
        print("CFB_STEP8_V14_SOURCE_GUARD_SUBMIT=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    @app.on_event("startup")
    def _run():
        Thread(target=_worker, name="cfb-step8-v14-source-guard-runless-submit", daemon=True).start()

    return app
