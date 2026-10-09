from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import _hash as frozen_hash, _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state

TASK_ID = "cfb-game-total-page1-visual-cleanup-step5-live-visual-cert"
WORKSTREAM = "cfb-game-total-page1-visual-cleanup-v1"
CANDIDATE_SHA = "c0cdf13130e56e97f195356ad81b2d386806eaf7"
MAIN_SHA = "0e2c11f03c1d3f6cb94756057ccb95e8ae74b2f9"
THAW_ID = "THAW-CFB-GT-P1-VISUAL-CLEANUP-STEP5-V191-ACTIVATION"
THAW_PATH = "streamlit_memory_lazy_router_v191.py"
FROM_BLOB = "1a4a2df127a060519d62ed96dd39f6c14bb79449"
TO_BLOB = "6f3b7132c75c360fd4d74c06e5e5b435435950f7"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
EXPECTED_REGISTRY_REVISION = 219
EXPECTED_REGISTRY_HASH = "7889ed5f5bffcde54416abaa5a2f820402505940193c03868fe68b7c2f473d39"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_ID = "SCOPE-LEASE-6B447CE36970CCC251A1A1CA"
LEASE_OWNER = "api2-cfb-game-total-page1-visual-cleanup-step5-convergence"


def _decode(raw, label):
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(label + "_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _holder(client):
    state = validate_scope_lease_state(_decode(client.content(LEASE_PATH, ref=LEASE_BRANCH), "STEP5_THAW_LEASE"))
    now = datetime.now(timezone.utc)
    return next((h for h in state.get("holders", []) if h.get("lease_id") == LEASE_ID and h.get("owner_id") == LEASE_OWNER and now < _utc(h["expires_at_utc"])), None)


def should_run(client):
    try:
        return _holder(client) is not None
    except Exception:
        return False


def _grant():
    return {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {THAW_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }


def execute(app):
    client = app.state.github_client
    holder = _holder(client)
    if holder is None:
        raise RuntimeError("STEP5_THAW_LEASE_NOT_LIVE")
    identity = (holder.get("scope") or {}).get("resource_identity") or {}
    expected = {
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": MAIN_SHA,
        "registry_state_hash": EXPECTED_REGISTRY_HASH,
        "repository": "kyrepeak/kyre-sports-ai",
        "workstream": WORKSTREAM,
    }
    if any(str(identity.get(k) or "") != v for k, v in expected.items()):
        raise RuntimeError("STEP5_THAW_IDENTITY_DRIFT")
    required = {
        REGISTRY_PATH,
        "runless_proof_plane/cfb_game_total_page1_visual_cleanup_step5_thaw.py",
        "runless_proof_plane/nfl_rb_wr_step3_closeout.py",
        THAW_PATH,
    }
    if not required.issubset(set((holder.get("scope") or {}).get("write_paths") or [])):
        raise RuntimeError("STEP5_THAW_SCOPE_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    current = _decode(raw, "STEP5_THAW_REGISTRY")
    validate_registry(current)
    if int(current.get("revision", -1)) != EXPECTED_REGISTRY_REVISION or str(current.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise RuntimeError("STEP5_THAW_REGISTRY_DRIFT")
    existing = next((g for g in current.get("active_thaws", []) if g.get("thaw_id") == THAW_ID), None)
    if existing == _grant():
        return {"status":"GREEN","decision":"STEP5_THAW_ALREADY_CORRECT","candidate_sha":CANDIDATE_SHA,"registry_revision":current["revision"],"registry_state_hash":current["state_hash"],"github_actions_fallback":0}
    if existing is None:
        raise RuntimeError("STEP5_THAW_RETARGET_SOURCE_MISSING")
    if existing.get("status") != "ACTIVE" or existing.get("files") != _grant()["files"]:
        raise RuntimeError("STEP5_THAW_RETARGET_BLOB_DRIFT")

    unrelated = [deepcopy(g) for g in (current.get("active_thaws") or []) if g.get("thaw_id") != THAW_ID]
    updated = deepcopy(current)
    updated["revision"] = EXPECTED_REGISTRY_REVISION + 1
    updated["source_main_sha"] = MAIN_SHA
    updated["active_thaws"] = unrelated + [_grant()]
    updated["state_hash"] = frozen_hash(_payload_without_hash(updated))
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        REGISTRY_BRANCH,
        "registry: retarget exact CFB Game Total Step5 V191 thaw",
        raw["sha"],
    )
    reread = _decode(client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH), "STEP5_THAW_READBACK")
    validate_registry(reread)
    if next((g for g in reread.get("active_thaws", []) if g.get("thaw_id") == THAW_ID), None) != _grant():
        raise RuntimeError("STEP5_THAW_READBACK_FAILED")
    if len(reread.get("active_thaws") or []) != len(unrelated) + 1:
        raise RuntimeError("STEP5_THAW_UNRELATED_DRIFT")
    return {
        "status": "GREEN",
        "decision": "STEP5_THAW_RETARGETED",
        "candidate_sha": CANDIDATE_SHA,
        "thaw_id": THAW_ID,
        "from_blob": FROM_BLOB,
        "to_blob": TO_BLOB,
        "registry_revision": reread["revision"],
        "registry_state_hash": reread["state_hash"],
        "unrelated_thaws_preserved": len(unrelated),
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_visual_cleanup_step5_thaw = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if not should_run(app.state.github_client):
            return
        try:
            app.state.cfb_game_total_visual_cleanup_step5_thaw = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_visual_cleanup_step5_thaw = {"status":"FAIL","error":type(exc).__name__,"detail":str(exc)[:1800]}
        print("CFB_GT_VISUAL_CLEANUP_STEP5_THAW=" + json.dumps(app.state.cfb_game_total_visual_cleanup_step5_thaw, sort_keys=True), flush=True)

    return app
