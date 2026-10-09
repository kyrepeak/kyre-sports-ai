from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import (
    _hash as frozen_hash,
    _payload_without_hash,
    validate_registry,
)
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state

TASK_ID = "cfb-game-total-page1-visual-cleanup-step3-overview-team-snapshot"
WORKSTREAM = "cfb-game-total-page1-visual-cleanup-v1"
CANDIDATE_SHA = "188b065e404141373c3f1157b7729243ef948e16"
MAIN_SHA = "036dbb2ab3a0e24ce3e1cb16c1b2f9469cfce2f4"
THAW_ID = "THAW-CFB-GT-P1-VISUAL-CLEANUP-STEP3-OVERVIEW"
THAW_PATH = "cfb_game_total_page1_v2_step4_side_market_completeness_v1.py"
FROM_BLOB = "b52cd7497388dbfe01a921014e13f9d99202cb84"
TO_BLOB = "f8ec957d95a8ebc152996195b97f366da41beb59"

REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
EXPECTED_REGISTRY_REVISION = 214
EXPECTED_REGISTRY_HASH = "b7dd28a4cc314d0962bb02a05eb7c27e892472f991382ceaa7936115da96f11c"

LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_ID = "SCOPE-LEASE-89A222D14A560722C1727D14"
LEASE_OWNER = "api2-cfb-game-total-page1-visual-cleanup-step3-thaw-finalizer"


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise RuntimeError(label + "_DECODE_FAILED") from exc


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _live_holder(client) -> dict | None:
    state = validate_scope_lease_state(
        _decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "CFB_GT_STEP3_THAW_LEASE")
    )
    now = datetime.now(timezone.utc)
    return next(
        (
            holder
            for holder in state.get("holders", [])
            if holder.get("lease_id") == LEASE_ID
            and holder.get("owner_id") == LEASE_OWNER
            and now < _utc(holder["expires_at_utc"])
        ),
        None,
    )


def should_run(client) -> bool:
    try:
        return _live_holder(client) is not None
    except Exception:
        return False


def _validate_authority(client) -> None:
    holder = _live_holder(client)
    if holder is None:
        raise RuntimeError("CFB_GT_STEP3_THAW_LEASE_NOT_LIVE")
    scope = holder.get("scope") or {}
    identity = scope.get("resource_identity") or {}
    expected = {
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": MAIN_SHA,
        "registry_state_hash": EXPECTED_REGISTRY_HASH,
        "repository": "kyrepeak/kyre-sports-ai",
        "workstream": WORKSTREAM,
    }
    if any(str(identity.get(key) or "") != value for key, value in expected.items()):
        raise RuntimeError("CFB_GT_STEP3_THAW_IDENTITY_DRIFT")
    required_paths = {
        REGISTRY_PATH,
        "runless_proof_plane/cfb_game_total_page1_visual_cleanup_step3_thaw.py",
        "runless_proof_plane/nfl_rb_wr_step3_closeout.py",
    }
    if not required_paths.issubset(set(scope.get("write_paths") or [])):
        raise RuntimeError("CFB_GT_STEP3_THAW_SCOPE_DRIFT")


def _grant() -> dict:
    return {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {
            THAW_PATH: {
                "from_blob": FROM_BLOB,
                "to_blob": TO_BLOB,
            }
        },
    }


def _existing_thaw(registry: dict) -> dict | None:
    return next(
        (grant for grant in registry.get("active_thaws", []) if grant.get("thaw_id") == THAW_ID),
        None,
    )


def _same_blob_pair(grant: dict) -> bool:
    pair = (grant.get("files") or {}).get(THAW_PATH) or {}
    return (
        str(pair.get("from_blob") or "") == FROM_BLOB
        and str(pair.get("to_blob") or "") == TO_BLOB
        and set(grant.get("files") or {}) == {THAW_PATH}
    )


def _readback(client, expected_revision: int, expected_hash: str) -> dict:
    registry = _decode_json(
        client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH),
        "CFB_GT_STEP3_THAW_REGISTRY_READBACK",
    )
    validated = validate_registry(registry)
    if int(registry.get("revision", -1)) != expected_revision:
        raise RuntimeError("CFB_GT_STEP3_THAW_REVISION_READBACK_DRIFT")
    if str(registry.get("state_hash") or "") != expected_hash:
        raise RuntimeError("CFB_GT_STEP3_THAW_HASH_READBACK_DRIFT")
    if _existing_thaw(registry) != _grant():
        raise RuntimeError("CFB_GT_STEP3_THAW_READBACK_MISMATCH")
    return {
        "revision": expected_revision,
        "state_hash": validated["state_hash"],
        "active_thaw_count": len(registry.get("active_thaws") or []),
    }


def execute(app) -> dict:
    client = app.state.github_client
    _validate_authority(client)

    registry_head = client.branch_sha(REGISTRY_BRANCH)
    raw = client.content(REGISTRY_PATH, ref=registry_head)
    current = _decode_json(raw, "CFB_GT_STEP3_THAW_REGISTRY")
    validated = validate_registry(current)

    existing = _existing_thaw(current)
    if existing == _grant():
        return {
            "status": "GREEN",
            "decision": "CFB_GT_STEP3_THAW_ALREADY_CORRECT",
            "task_id": TASK_ID,
            "candidate_sha": CANDIDATE_SHA,
            "thaw_id": THAW_ID,
            "registry_revision": int(current["revision"]),
            "registry_state_hash": str(current["state_hash"]),
            "active_thaw_count": len(current.get("active_thaws") or []),
            "github_actions_fallback": 0,
        }

    if int(current.get("revision", -1)) != EXPECTED_REGISTRY_REVISION:
        raise RuntimeError("CFB_GT_STEP3_THAW_REGISTRY_REVISION_DRIFT")
    if str(current.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise RuntimeError("CFB_GT_STEP3_THAW_REGISTRY_HASH_DRIFT")
    if validated["artifacts"].get(THAW_PATH) != FROM_BLOB:
        raise RuntimeError("CFB_GT_STEP3_THAW_BASELINE_DRIFT")
    if existing is None or not _same_blob_pair(existing):
        raise RuntimeError("CFB_GT_STEP3_THAW_STALE_GRANT_SHAPE_DRIFT")

    unrelated = [
        deepcopy(grant)
        for grant in current.get("active_thaws", [])
        if grant.get("thaw_id") != THAW_ID
    ]
    if any(THAW_PATH in (grant.get("files") or {}) for grant in unrelated):
        raise RuntimeError("CFB_GT_STEP3_THAW_PATH_CONFLICT")

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
        "registry: retarget exact CFB Game Total visual cleanup Step3 thaw",
        raw["sha"],
    )
    readback = _readback(client, int(updated["revision"]), str(updated["state_hash"]))
    if readback["active_thaw_count"] != len(unrelated) + 1:
        raise RuntimeError("CFB_GT_STEP3_THAW_UNRELATED_THAW_DRIFT")

    return {
        "status": "GREEN",
        "decision": "CFB_GT_STEP3_THAW_TARGET_REPLACED",
        "task_id": TASK_ID,
        "candidate_sha": CANDIDATE_SHA,
        "thaw_id": THAW_ID,
        "thaw_path": THAW_PATH,
        "from_blob": FROM_BLOB,
        "to_blob": TO_BLOB,
        "registry_revision": readback["revision"],
        "registry_state_hash": readback["state_hash"],
        "unrelated_thaws_preserved": len(unrelated),
        "active_thaw_count": readback["active_thaw_count"],
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_visual_cleanup_step3_thaw = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if not should_run(app.state.github_client):
            return
        try:
            app.state.cfb_game_total_visual_cleanup_step3_thaw = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_visual_cleanup_step3_thaw = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_VISUAL_CLEANUP_STEP3_THAW="
            + json.dumps(app.state.cfb_game_total_visual_cleanup_step3_thaw, sort_keys=True),
            flush=True,
        )

    return app
