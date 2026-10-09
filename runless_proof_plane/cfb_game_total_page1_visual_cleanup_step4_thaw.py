from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import _hash as frozen_hash, _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state

TASK_ID = "cfb-game-total-page1-visual-cleanup-step4-footer-evidence"
WORKSTREAM = "cfb-game-total-page1-visual-cleanup-v1"
CANDIDATE_SHA = "a86d20ba402ff52286b8e5431098ca0bb849bc39"
MAIN_SHA = "5c7373ecb1c5c042db0909cc9f7d9e6c64ba43ff"
THAW_ID = "THAW-CFB-GT-P1-VISUAL-CLEANUP-STEP4-FOOTER-EVIDENCE"
THAW_PATH = "cfb_game_total_page1_v2_step4_side_market_completeness_v1.py"
FROM_BLOB = "f8ec957d95a8ebc152996195b97f366da41beb59"
TO_BLOB = "e48996d53a7a51a102c57e7b822ee269cd750899"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
EXPECTED_REGISTRY_REVISION = 216
EXPECTED_REGISTRY_HASH = "ba1aadd2a9f83589f0363535fadd573be0d1904bf98cb42f2644b5e96438b08d"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_ID = "SCOPE-LEASE-71C3421DD0BC1ECA1BC643D7"
LEASE_OWNER = "api2-cfb-game-total-page1-visual-cleanup-step4-convergence"


def _decode(raw, label):
    if not raw or raw.get("encoding") != "base64": raise RuntimeError(label + "_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _holder(client):
    state = validate_scope_lease_state(_decode(client.content(LEASE_PATH, ref=LEASE_BRANCH), "STEP4_THAW_LEASE"))
    now = datetime.now(timezone.utc)
    return next((h for h in state.get("holders", []) if h.get("lease_id") == LEASE_ID and h.get("owner_id") == LEASE_OWNER and now < _utc(h["expires_at_utc"])), None)


def should_run(client):
    try: return _holder(client) is not None
    except Exception: return False


def _grant():
    return {"thaw_id": THAW_ID, "status": "ACTIVE", "target_head_sha": CANDIDATE_SHA, "files": {THAW_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}}}


def execute(app):
    client = app.state.github_client
    holder = _holder(client)
    if holder is None: raise RuntimeError("STEP4_THAW_LEASE_NOT_LIVE")
    identity = (holder.get("scope") or {}).get("resource_identity") or {}
    expected = {"candidate_sha": CANDIDATE_SHA, "main_sha": MAIN_SHA, "registry_state_hash": EXPECTED_REGISTRY_HASH, "repository": "kyrepeak/kyre-sports-ai", "workstream": WORKSTREAM}
    if any(str(identity.get(k) or "") != v for k, v in expected.items()): raise RuntimeError("STEP4_THAW_IDENTITY_DRIFT")
    required = {REGISTRY_PATH, "runless_proof_plane/cfb_game_total_page1_visual_cleanup_step4_thaw.py", "runless_proof_plane/nfl_rb_wr_step3_closeout.py"}
    if not required.issubset(set((holder.get("scope") or {}).get("write_paths") or [])): raise RuntimeError("STEP4_THAW_SCOPE_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    current = _decode(raw, "STEP4_THAW_REGISTRY")
    validated = validate_registry(current)
    existing = next((g for g in current.get("active_thaws", []) if g.get("thaw_id") == THAW_ID), None)
    if existing == _grant():
        return {"status":"GREEN","decision":"STEP4_THAW_ALREADY_CORRECT","candidate_sha":CANDIDATE_SHA,"registry_revision":current["revision"],"registry_state_hash":current["state_hash"],"github_actions_fallback":0}
    if existing is not None: raise RuntimeError("STEP4_THAW_DUPLICATE_ID_DRIFT")
    if int(current.get("revision", -1)) != EXPECTED_REGISTRY_REVISION or str(current.get("state_hash") or "") != EXPECTED_REGISTRY_HASH: raise RuntimeError("STEP4_THAW_REGISTRY_DRIFT")
    if validated["artifacts"].get(THAW_PATH) != FROM_BLOB: raise RuntimeError("STEP4_THAW_BASELINE_DRIFT")
    if any(THAW_PATH in (g.get("files") or {}) for g in current.get("active_thaws", [])): raise RuntimeError("STEP4_THAW_PATH_CONFLICT")

    unrelated = deepcopy(current.get("active_thaws") or [])
    updated = deepcopy(current)
    updated["revision"] = EXPECTED_REGISTRY_REVISION + 1
    updated["source_main_sha"] = MAIN_SHA
    updated["active_thaws"] = unrelated + [_grant()]
    updated["state_hash"] = frozen_hash(_payload_without_hash(updated))
    validate_registry(updated)
    client.update_content(REGISTRY_PATH, json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n", REGISTRY_BRANCH, "registry: grant exact CFB Game Total visual cleanup Step4 thaw", raw["sha"])
    reread = _decode(client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH), "STEP4_THAW_READBACK")
    validate_registry(reread)
    if next((g for g in reread.get("active_thaws", []) if g.get("thaw_id") == THAW_ID), None) != _grant(): raise RuntimeError("STEP4_THAW_READBACK_FAILED")
    if len(reread.get("active_thaws") or []) != len(unrelated) + 1: raise RuntimeError("STEP4_THAW_UNRELATED_DRIFT")
    return {"status":"GREEN","decision":"STEP4_THAW_GRANTED","candidate_sha":CANDIDATE_SHA,"thaw_id":THAW_ID,"from_blob":FROM_BLOB,"to_blob":TO_BLOB,"registry_revision":reread["revision"],"registry_state_hash":reread["state_hash"],"unrelated_thaws_preserved":len(unrelated),"github_actions_fallback":0}


def install_startup(app):
    app.state.cfb_game_total_visual_cleanup_step4_thaw = {"status":"NOT_RUN"}
    @app.on_event("startup")
    def _run():
        if not should_run(app.state.github_client): return
        try: app.state.cfb_game_total_visual_cleanup_step4_thaw = execute(app)
        except Exception as exc: app.state.cfb_game_total_visual_cleanup_step4_thaw = {"status":"FAIL","error":type(exc).__name__,"detail":str(exc)[:1800]}
        print("CFB_GT_VISUAL_CLEANUP_STEP4_THAW=" + json.dumps(app.state.cfb_game_total_visual_cleanup_step4_thaw, sort_keys=True), flush=True)
    return app
