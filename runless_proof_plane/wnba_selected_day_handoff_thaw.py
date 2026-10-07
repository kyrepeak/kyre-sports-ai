from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

MAIN_SHA = "2800670d1b1e15f6a98cc7a5fc3ffab4fb9600e5"
BRANCH = "api2-wnba-data-step2-selected-day-handoff-r1"
CANDIDATE_SHA = "786d3042e5c3392edc3a40218520aff5d9e1a934"
PATH = "wnba_availability_v27.py"
FROM_BLOB = "82468c9b603947c052e726cd8beb9ba1b05b2484"
TO_BLOB = "4cdb65b9fd7942865ad17e7b27e29fb815192de1"
OWNER_TOKEN = "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP1_FROZEN"
THAW_ID = "THAW-API2-WNBA-DATA-STEP2-SELECTED-DAY-HANDOFF-R1"
EXPECTED_REVISION = 153
EXPECTED_HASH = "8632c536568197f0b772fafe1bea8dacb871c087af7dcfd590537356073e9dec"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("SELECTED_DAY_THAW_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("SELECTED_DAY_THAW_CANDIDATE_DRIFT")

    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if str(main_tree.get(PATH) or "") != FROM_BLOB:
        raise RuntimeError("SELECTED_DAY_THAW_MAIN_BLOB_DRIFT")
    if str(candidate_tree.get(PATH) or "") != TO_BLOB:
        raise RuntimeError("SELECTED_DAY_THAW_CANDIDATE_BLOB_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("SELECTED_DAY_THAW_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise RuntimeError("SELECTED_DAY_THAW_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise RuntimeError("SELECTED_DAY_THAW_HASH_DRIFT")

    owner = ((registry.get("entries") or {}).get(OWNER_TOKEN) or {}).get("artifacts") or {}
    if str(owner.get(PATH) or "") != FROM_BLOB:
        raise RuntimeError("SELECTED_DAY_THAW_OWNER_BASELINE_DRIFT")

    thaws = deepcopy(list(registry.get("active_thaws") or []))
    if any(PATH in (item.get("files") or {}) for item in thaws):
        raise RuntimeError("SELECTED_DAY_THAW_PATH_ALREADY_ACTIVE")
    if any(item.get("thaw_id") == THAW_ID for item in thaws):
        raise RuntimeError("SELECTED_DAY_THAW_ID_EXISTS")

    grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
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
        raise RuntimeError("SELECTED_DAY_THAW_READBACK_FAILED")
    unrelated_after = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    if unrelated_after != thaws:
        raise RuntimeError("SELECTED_DAY_THAW_UNRELATED_DRIFT")

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
    app.state.wnba_selected_day_handoff_thaw = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_selected_day_handoff_thaw = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_selected_day_handoff_thaw = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print(
            "WNBA_SELECTED_DAY_HANDOFF_THAW="
            + json.dumps(app.state.wnba_selected_day_handoff_thaw, sort_keys=True),
            flush=True,
        )
    return app
