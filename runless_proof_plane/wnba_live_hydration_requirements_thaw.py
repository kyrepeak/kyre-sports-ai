from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

MAIN_SHA = "b5bda426136ea7ac8ed2d07308a077db0f8aee4f"
BRANCH = "api2-wnba-data-step2-live-hydration-streamlit-refresh-r1"
CANDIDATE_SHA = "b6ab705d7de96b0c8d779abf1f8baa7ab46efbce"
PATH = "requirements.txt"
CURRENT_MAIN_BLOB = "d2f2157e65e36cdc46410fc897b3f0cb8d3890a8"
CANDIDATE_BLOB = "890ba18abaf02a53cba8929b87bce110e2599dbe"
OWNER_TOKEN = "WNBA_PRA_REPAIR_V1_STEP8_FROZEN"
OWNER_HISTORICAL_BLOB = "98b621afd372d472784850fed4b603c9989dcf7a"
THAW_ID = "THAW-API2-WNBA-DATA-STEP2-STREAMLIT-REFRESH-R1"
EXPECTED_REVISION = 152
EXPECTED_HASH = "b9f957642985f34412f27c4ea9ef0c932787b059bef35bda80364de299a23ba0"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("REQUIREMENTS_THAW_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("REQUIREMENTS_THAW_CANDIDATE_DRIFT")
    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if str(main_tree.get(PATH) or "") != CURRENT_MAIN_BLOB:
        raise RuntimeError("REQUIREMENTS_THAW_MAIN_BLOB_DRIFT")
    if str(candidate_tree.get(PATH) or "") != CANDIDATE_BLOB:
        raise RuntimeError("REQUIREMENTS_THAW_CANDIDATE_BLOB_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("REQUIREMENTS_THAW_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise RuntimeError("REQUIREMENTS_THAW_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise RuntimeError("REQUIREMENTS_THAW_HASH_DRIFT")
    owner = ((registry.get("entries") or {}).get(OWNER_TOKEN) or {}).get("artifacts") or {}
    if str(owner.get(PATH) or "") != OWNER_HISTORICAL_BLOB:
        raise RuntimeError("REQUIREMENTS_THAW_OWNER_DRIFT")

    thaws = deepcopy(list(registry.get("active_thaws") or []))
    if any(PATH in (item.get("files") or {}) for item in thaws):
        raise RuntimeError("REQUIREMENTS_THAW_PATH_ALREADY_ACTIVE")
    if any(item.get("thaw_id") == THAW_ID for item in thaws):
        raise RuntimeError("REQUIREMENTS_THAW_ID_EXISTS")

    grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {PATH: {"from_blob": CURRENT_MAIN_BLOB, "to_blob": CANDIDATE_BLOB}},
    }
    updated = deepcopy(registry)
    updated.setdefault("active_thaws", []).append(grant)
    updated["revision"] = int(registry["revision"]) + 1
    updated["source_main_sha"] = MAIN_SHA
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        REGISTRY_BRANCH,
        f"registry: thaw {THAW_ID}",
        str(raw["sha"]),
    )

    rb_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    rb = json.loads(base64.b64decode(rb_raw["content"]).decode())
    validate_registry(rb)
    matches = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if matches != [grant]:
        raise RuntimeError("REQUIREMENTS_THAW_READBACK_FAILED")
    unrelated_after = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    if unrelated_after != thaws:
        raise RuntimeError("REQUIREMENTS_THAW_UNRELATED_DRIFT")
    return {
        "status": "GREEN",
        "thaw_id": THAW_ID,
        "candidate_sha": CANDIDATE_SHA,
        "registry_revision": int(rb["revision"]),
        "registry_state_hash": str(rb["state_hash"]),
        "unrelated_thaws_preserved": len(unrelated_after),
        "main_mutated": False,
    }


def install_startup(app):
    app.state.wnba_live_hydration_requirements_thaw = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_live_hydration_requirements_thaw = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_live_hydration_requirements_thaw = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print("WNBA_LIVE_HYDRATION_REQUIREMENTS_THAW=" + json.dumps(app.state.wnba_live_hydration_requirements_thaw, sort_keys=True), flush=True)
    return app
