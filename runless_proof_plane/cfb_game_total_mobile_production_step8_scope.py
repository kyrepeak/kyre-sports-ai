from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import _hash as registry_hash, _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import build_scope, claim_scope, release_scope, validate_state as validate_scope_state

from .registry import GithubRegistryBackend, REGISTRY_PATH

TASK_ID = "cfb-game-total-mobile-production-step8-premerge-v1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
BRANCH = "cfb-game-total-mobile-production-step8-v1"
CANDIDATE_SHA = "b7c5bb3c1f7a00a3f2836a62d832c269e2bd4369"
MAIN_SHA = "36e0d3ee8de1a72bdeeb5e007334df1e8c5a3adb"
THAW_ID = "THAW-CFB-GT-MOBILE-PRODUCTION-STEP8-R1"
FROZEN_PATH = "cfb_game_total_clean_page_v43.py"
FROM_BLOB = "ebb7bfa20489598a62891ec4e5e868fe350c8712"
TO_BLOB = "33b032014ddb8d9316e9282510d896ec61df603a"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8"
WRITE_PATHS = (
    FROZEN_PATH,
    "devsystem/cfb_game_total_mobile_production_step8_v1.py",
    "devsystem/production_targets_v1.json",
    "tests/test_cfb_game_total_mobile_production_step8_v1.py",
    "tests/test_cfb_game_total_page1_default_selection_step8_v1.py",
    "devsystem/runless_proof_plans/cfb-game-total-mobile-production-step8-premerge-v1.json",
    "devsystem/runless_proof_plans/cfb-game-total-mobile-production-step8-v1.json",
    "devsystem/task_ledgers/cfb-game-total-mobile-production-step8-v1.json",
)


class Step8ScopeFailure(RuntimeError):
    pass


def _json_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise Step8ScopeFailure(label + "_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _verify_heads(client) -> None:
    if client.branch_sha("main") != MAIN_SHA:
        raise Step8ScopeFailure("MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise Step8ScopeFailure("CANDIDATE_DRIFT")
    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if str(main_tree.get(FROZEN_PATH) or "") != FROM_BLOB:
        raise Step8ScopeFailure("FROZEN_FROM_BLOB_DRIFT")
    if str(candidate_tree.get(FROZEN_PATH) or "") != TO_BLOB:
        raise Step8ScopeFailure("FROZEN_TO_BLOB_DRIFT")
    for path in WRITE_PATHS:
        if not candidate_tree.get(path):
            raise Step8ScopeFailure("CANDIDATE_ARTIFACT_MISSING:" + path)


def _ensure_thaw(client) -> dict:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    if str(registry.get("source_main_sha") or "") != MAIN_SHA:
        raise Step8ScopeFailure("REGISTRY_SOURCE_MAIN_DRIFT")
    exact = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {FROZEN_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }
    matches = [g for g in registry.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    if len(matches) > 1:
        raise Step8ScopeFailure("THAW_DUPLICATE")
    if matches == [exact]:
        return {
            "created": False,
            "refreshed": False,
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
            "active_thaw_count": len(registry.get("active_thaws", [])),
        }
    before_unrelated = [deepcopy(g) for g in registry.get("active_thaws", []) if g.get("thaw_id") != THAW_ID]
    if matches:
        stale = matches[0]
        if stale.get("status") != "ACTIVE" or stale.get("files") != exact["files"]:
            raise Step8ScopeFailure("THAW_ID_COLLISION")
    updated = deepcopy(registry)
    updated["active_thaws"] = sorted(before_unrelated + [exact], key=lambda row: str(row.get("thaw_id") or ""))
    updated["revision"] = int(updated["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        _json_text(updated),
        backend.branch,
        "registry: refresh CFB Game Total Step 8 Page1 exact thaw target",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    found = [g for g in readback.get("active_thaws", []) if g.get("thaw_id") == THAW_ID]
    if found != [exact]:
        raise Step8ScopeFailure("THAW_READBACK_MISMATCH")
    unrelated_after = [g for g in readback.get("active_thaws", []) if g.get("thaw_id") != THAW_ID]
    if unrelated_after != before_unrelated:
        raise Step8ScopeFailure("UNRELATED_THAW_DRIFT")
    return {
        "created": not bool(matches),
        "refreshed": bool(matches),
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "active_thaw_count": len(readback.get("active_thaws", [])),
    }


def _ensure_lease(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode_json(raw, "LEASE"))
    owned = [h for h in state.get("holders", []) if h.get("owner_id") == LEASE_OWNER]
    exact = [h for h in owned if (h.get("scope") or {}).get("resource_identity", {}).get("candidate_sha") == CANDIDATE_SHA]
    if exact:
        if len(owned) != 1 or len(exact) != 1:
            raise Step8ScopeFailure("LEASE_DUPLICATE")
        return {
            "created": False,
            "lease_id": str(exact[0]["lease_id"]),
            "revision": int(state["revision"]),
            "state_hash": str(state["state_hash"]),
        }
    working = state
    released_id = ""
    if owned:
        if len(owned) != 1:
            raise Step8ScopeFailure("LEASE_DUPLICATE")
        released_id = str(owned[0]["lease_id"])
        released = release_scope(
            working,
            owner_id=LEASE_OWNER,
            lease_id=released_id,
            expected_revision=int(working["revision"]),
            expected_state_hash=str(working["state_hash"]),
        )
        if released["result"].get("allowed") is not True:
            raise Step8ScopeFailure("STALE_LEASE_RELEASE_BLOCKED")
        working = released["state"]
    scope = build_scope(
        write_paths=WRITE_PATHS,
        dependency_tokens=("cfb:game-total:step8", "cfb:game-total:page1-event-handoff"),
        shared_resources=("route:cfb:game-total", "presentation:cfb:game-total:page1", "certification:cfb:game-total"),
        resource_identity={"candidate_sha": CANDIDATE_SHA, "main_sha": MAIN_SHA},
        exclusive=False,
    )
    claimed = claim_scope(
        working,
        owner_id=LEASE_OWNER,
        now_utc=_now(),
        scope=scope,
        expected_revision=int(working["revision"]),
        expected_state_hash=str(working["state_hash"]),
        ttl_seconds=3600,
        frozen_paths=(FROZEN_PATH,),
        thawed_paths=(FROZEN_PATH,),
    )
    if claimed["result"].get("allowed") is not True:
        raise Step8ScopeFailure("LEASE_BLOCKED:" + str(claimed["result"].get("decision") or "UNKNOWN"))
    updated = claimed["state"]
    holders = [h for h in updated.get("holders", []) if h.get("owner_id") == LEASE_OWNER]
    if len(holders) != 1:
        raise Step8ScopeFailure("LEASE_ID_UNRESOLVED")
    lease_id = str(holders[0]["lease_id"])
    client.update_content(
        LEASE_PATH,
        _json_text(updated),
        LEASE_BRANCH,
        "lease: refresh CFB Game Total Step 8 exact scope",
        raw["sha"],
    )
    readback = validate_scope_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "LEASE_READBACK"))
    found = [h for h in readback.get("holders", []) if h.get("lease_id") == lease_id and h.get("owner_id") == LEASE_OWNER]
    if len(found) != 1:
        raise Step8ScopeFailure("LEASE_READBACK_MISMATCH")
    return {
        "created": True,
        "replaced": bool(released_id),
        "released_lease_id": released_id,
        "lease_id": lease_id,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
    }


def execute(app):
    client = app.state.github_client
    _verify_heads(client)
    thaw = _ensure_thaw(client)
    lease = _ensure_lease(client)
    return {
        "status": "GREEN",
        "decision": "STEP8_SCOPE_AUTHORIZED",
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": MAIN_SHA,
        "thaw": thaw,
        "lease": lease,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_step8_scope = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_step8_scope = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_step8_scope = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:4200],
            }
        print("CFB_GAME_TOTAL_STEP8_SCOPE=" + json.dumps(app.state.cfb_game_total_step8_scope, sort_keys=True, default=str), flush=True)

    return app


__all__ = ["execute", "install_startup"]
