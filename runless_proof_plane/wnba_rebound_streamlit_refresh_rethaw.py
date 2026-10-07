from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

MAIN_SHA = "c23faa12367275d19d140460a09d83164ab5de2a"
BRANCH = "api2-wnba-data-step2-rebound-streamlit-refresh-r1"
CANDIDATE_SHA = "9bedbdd848985c42c691018a0952142714f3bf43"
PATH = "requirements.txt"
FROM_BLOB = "98b621afd372d472784850fed4b603c9989dcf7a"
OLD_TO_BLOB = "890ba18abaf02a53cba8929b87bce110e2599dbe"
TO_BLOB = "7f5cf407662a79cb4c56781195e7bbcaca38d315"
THAW_ID = "THAW-API2-WNBA-DATA-STEP2-STREAMLIT-REFRESH-R1"
OLD_TARGET = "b6ab705d7de96b0c8d779abf1f8baa7ab46efbce"
EXPECTED_REVISION = 154
EXPECTED_HASH = "63d54f1a303062167e651073dd410dd79bbc3917d5e15c5c737ab7520404f55c"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("REB_REFRESH_RETHAW_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("REB_REFRESH_RETHAW_CANDIDATE_DRIFT")
    tree = client.tree_blobs(CANDIDATE_SHA)
    if str(tree.get(PATH) or "") != TO_BLOB:
        raise RuntimeError("REB_REFRESH_RETHAW_BLOB_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("REB_REFRESH_RETHAW_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise RuntimeError("REB_REFRESH_RETHAW_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise RuntimeError("REB_REFRESH_RETHAW_HASH_DRIFT")

    thaws = deepcopy(list(registry.get("active_thaws") or []))
    matches = [item for item in thaws if item.get("thaw_id") == THAW_ID]
    if len(matches) != 1:
        raise RuntimeError("REB_REFRESH_RETHAW_EXISTING_GRANT_MISSING")
    old = matches[0]
    pair = (old.get("files") or {}).get(PATH) or {}
    if str(old.get("target_head_sha") or "") != OLD_TARGET:
        raise RuntimeError("REB_REFRESH_RETHAW_OLD_TARGET_DRIFT")
    if str(pair.get("from_blob") or "") != FROM_BLOB or str(pair.get("to_blob") or "") != OLD_TO_BLOB:
        raise RuntimeError("REB_REFRESH_RETHAW_OLD_BLOB_DRIFT")
    for item in thaws:
        if item.get("thaw_id") != THAW_ID and PATH in (item.get("files") or {}):
            raise RuntimeError("REB_REFRESH_RETHAW_COMPETING_THAW")

    grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }
    unrelated_before = [item for item in thaws if item.get("thaw_id") != THAW_ID]
    updated = deepcopy(registry)
    updated["active_thaws"] = [grant if item.get("thaw_id") == THAW_ID else item for item in thaws]
    updated["revision"] = int(registry["revision"]) + 1
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        REGISTRY_BRANCH,
        f"registry: roll forward {THAW_ID} for rebound refresh",
        str(raw["sha"]),
    )

    rb_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    rb = json.loads(base64.b64decode(rb_raw["content"]).decode())
    validate_registry(rb)
    rb_matches = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if rb_matches != [grant]:
        raise RuntimeError("REB_REFRESH_RETHAW_READBACK_FAILED")
    unrelated_after = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    if unrelated_after != unrelated_before:
        raise RuntimeError("REB_REFRESH_RETHAW_UNRELATED_DRIFT")
    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "thaw_id": THAW_ID,
        "registry_revision": int(rb["revision"]),
        "registry_state_hash": str(rb["state_hash"]),
        "from_blob": FROM_BLOB,
        "to_blob": TO_BLOB,
        "unrelated_thaws_preserved": len(unrelated_after),
        "main_mutated": False,
    }


def install_startup(app):
    app.state.wnba_rebound_streamlit_refresh_rethaw = {"status": "NOT_RUN"}
    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_rebound_streamlit_refresh_rethaw = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_rebound_streamlit_refresh_rethaw = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print("WNBA_REBOUND_STREAMLIT_REFRESH_RETHAW=" + json.dumps(app.state.wnba_rebound_streamlit_refresh_rethaw, sort_keys=True), flush=True)
    return app
