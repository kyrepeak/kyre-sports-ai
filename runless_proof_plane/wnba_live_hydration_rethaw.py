from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

MAIN_SHA = "c038037f0c7f9e1a6338c2ca29bdcae08e15fae7"
REPAIR_BRANCH = "api2-wnba-data-completeness-repair-v1-step2-live-hydration-r1"
CANDIDATE_SHA = "54e3fe375cb22fc53c844ba50bb6dd04f45e7482"
RUNTIME_PATH = "wnba_players_v25.py"
FROM_BLOB = "9960efb20d9e6f3791ed5c3228ca42abd884f828"
TO_BLOB = "13055f7bc06a8af369daba47453e92fe7e6c8ea7"
STEP2_TOKEN = "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP2_FROZEN"
THAW_ID = "THAW-API2-WNBA-DATA-STEP2-LIVE-HYDRATION-R2"
EXPECTED_REVISION = 151
EXPECTED_HASH = "90d57744cbc652e6175d25b8afa7aeefc2ab4453b6bb7b1b8ade324c93e14fc6"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("RETHAW_MAIN_DRIFT")
    if client.branch_sha(REPAIR_BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("RETHAW_CANDIDATE_HEAD_DRIFT")
    tree = client.tree_blobs(CANDIDATE_SHA)
    if str(tree.get(RUNTIME_PATH) or "") != TO_BLOB:
        raise RuntimeError("RETHAW_CANDIDATE_BLOB_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("RETHAW_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise RuntimeError("RETHAW_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise RuntimeError("RETHAW_HASH_DRIFT")
    frozen = ((registry.get("entries") or {}).get(STEP2_TOKEN) or {}).get("artifacts") or {}
    if str(frozen.get(RUNTIME_PATH) or "") != FROM_BLOB:
        raise RuntimeError("RETHAW_FROZEN_BASELINE_DRIFT")
    thaws = deepcopy(list(registry.get("active_thaws") or []))
    if any(RUNTIME_PATH in (item.get("files") or {}) for item in thaws):
        raise RuntimeError("RETHAW_RUNTIME_ALREADY_THAWED")
    if any(item.get("thaw_id") == THAW_ID for item in thaws):
        raise RuntimeError("RETHAW_ID_EXISTS")

    grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {RUNTIME_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }
    updated = deepcopy(registry)
    updated.setdefault("active_thaws", []).append(grant)
    updated["revision"] = int(registry["revision"]) + 1
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        REGISTRY_BRANCH,
        f"registry: re-authorize {THAW_ID}",
        str(raw["sha"]),
    )

    rb_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    rb = json.loads(base64.b64decode(rb_raw["content"]).decode())
    validate_registry(rb)
    matches = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if matches != [grant]:
        raise RuntimeError("RETHAW_READBACK_FAILED")
    unrelated_before = thaws
    unrelated_after = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    if unrelated_after != unrelated_before:
        raise RuntimeError("RETHAW_UNRELATED_THAW_DRIFT")
    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "thaw_id": THAW_ID,
        "registry_revision": int(rb["revision"]),
        "registry_state_hash": str(rb["state_hash"]),
        "unrelated_thaws_preserved": len(unrelated_after),
        "main_mutated": False,
    }


def install_startup(app):
    app.state.wnba_live_hydration_rethaw = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_live_hydration_rethaw = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_live_hydration_rethaw = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]}
        print("WNBA_LIVE_HYDRATION_RETHAW=" + json.dumps(app.state.wnba_live_hydration_rethaw, sort_keys=True), flush=True)
    return app
