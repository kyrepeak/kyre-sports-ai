from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

MAIN_SHA = "4036459c8c8cde0ac8f3034b560d7948ad9a5015"
BRANCH = "api2-wnba-data-step3-recent-form-h2h-r1"
CANDIDATE_SHA = "7e4b30afd24d6b4921d4936f1d9b44d959756793"
PATH = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration.py"
FROM_BLOB = "6aeb31c68c9e4637aa87d50a70e381e283fc08f7"
TO_BLOB = "a6015096c12684e7456b19ed02ee18cf02dbc7d2"
THAW_ID = "THAW-API2-WNBA-DATA-STEP3-PLAYER-SHELL-HANDOFF-R1"
EXPECTED_REVISION = 159
EXPECTED_HASH = "232407f3cfef74dd7eb133a79b81930f15ed5fb31ff5bd74f33d64c3e5839b01"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("WNBA_DATA_STEP3_THAW_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("WNBA_DATA_STEP3_THAW_CANDIDATE_DRIFT")

    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if str(main_tree.get(PATH) or "") != FROM_BLOB:
        raise RuntimeError("WNBA_DATA_STEP3_THAW_MAIN_BLOB_DRIFT")
    if str(candidate_tree.get(PATH) or "") != TO_BLOB:
        raise RuntimeError("WNBA_DATA_STEP3_THAW_CANDIDATE_BLOB_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP3_THAW_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise RuntimeError("WNBA_DATA_STEP3_THAW_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise RuntimeError("WNBA_DATA_STEP3_THAW_HASH_DRIFT")

    owners = []
    for token, entry in (registry.get("entries") or {}).items():
        artifacts = entry.get("artifacts") or {}
        if PATH in artifacts:
            owners.append((str(token), str(artifacts[PATH])))
    if not owners:
        raise RuntimeError("WNBA_DATA_STEP3_THAW_OWNER_MISSING")
    if any(blob != FROM_BLOB for _, blob in owners):
        raise RuntimeError("WNBA_DATA_STEP3_THAW_OWNER_BASELINE_DRIFT")

    thaws = deepcopy(list(registry.get("active_thaws") or []))
    if any(PATH in (item.get("files") or {}) for item in thaws):
        raise RuntimeError("WNBA_DATA_STEP3_THAW_PATH_ALREADY_ACTIVE")
    if any(item.get("thaw_id") == THAW_ID for item in thaws):
        raise RuntimeError("WNBA_DATA_STEP3_THAW_ID_EXISTS")

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
        raise RuntimeError("WNBA_DATA_STEP3_THAW_READBACK_FAILED")
    unrelated_after = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    if unrelated_after != thaws:
        raise RuntimeError("WNBA_DATA_STEP3_THAW_UNRELATED_DRIFT")

    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "thaw_id": THAW_ID,
        "registry_revision": int(rb["revision"]),
        "registry_state_hash": str(rb["state_hash"]),
        "owner_tokens": [token for token, _ in owners],
        "unrelated_thaws_preserved": len(unrelated_after),
        "main_mutated": False,
    }


def install_startup(app):
    app.state.wnba_data_step3_player_shell_thaw = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_data_step3_player_shell_thaw = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step3_player_shell_thaw = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print(
            "WNBA_DATA_STEP3_PLAYER_SHELL_THAW="
            + json.dumps(app.state.wnba_data_step3_player_shell_thaw, sort_keys=True),
            flush=True,
        )
    return app
