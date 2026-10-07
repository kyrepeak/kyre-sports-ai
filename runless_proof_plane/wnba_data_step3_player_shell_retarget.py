from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

MAIN_SHA = "d908cdc3e8ea4b0224333268e7b02d0af3bd9063"
BRANCH = "api2-wnba-data-step3-recent-form-h2h-r1"
OLD_CANDIDATE_SHA = "212f63213b617f10a7247e70aef57e40a1112ff4"
NEW_CANDIDATE_SHA = "fb7584133e4e7d54cb958b3593d28b0a25d4aed7"
PATH = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration.py"
FROZEN_BLOB = "6aeb31c68c9e4637aa87d50a70e381e283fc08f7"
MAIN_BLOB = "deeb6a9de5270d2d3745c620129895b90ef2b688"
OLD_TO_BLOB = "03e39d6c86f6cff93067417ed0c0a6788d04fff0"
NEW_BLOB = "7c5c8bee3299dae7faebc3d22953a2a1b9fa2dcc"
THAW_ID = "THAW-API2-WNBA-DATA-STEP3-PLAYER-SHELL-HANDOFF-R1"
EXPECTED_REVISION = 163
EXPECTED_HASH = "1600f7d006c2e2ee52aa346afa595d687150885a33202136e6fea54e49db75a3"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("WNBA_DATA_STEP3_RETARGET_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != OLD_CANDIDATE_SHA:
        raise RuntimeError("WNBA_DATA_STEP3_RETARGET_BRANCH_DRIFT")

    main_tree = client.tree_blobs(MAIN_SHA)
    new_tree = client.tree_blobs(NEW_CANDIDATE_SHA)
    if str(main_tree.get(PATH) or "") != MAIN_BLOB:
        raise RuntimeError("WNBA_DATA_STEP3_RETARGET_MAIN_BLOB_DRIFT")
    if str(new_tree.get(PATH) or "") != NEW_BLOB:
        raise RuntimeError("WNBA_DATA_STEP3_RETARGET_NEW_BLOB_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP3_RETARGET_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise RuntimeError("WNBA_DATA_STEP3_RETARGET_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise RuntimeError("WNBA_DATA_STEP3_RETARGET_HASH_DRIFT")

    owners = []
    for token, entry in (registry.get("entries") or {}).items():
        artifacts = entry.get("artifacts") or {}
        if PATH in artifacts:
            owners.append((str(token), str(artifacts[PATH])))
    if not owners or any(blob != FROZEN_BLOB for _, blob in owners):
        raise RuntimeError("WNBA_DATA_STEP3_RETARGET_OWNER_DRIFT")

    thaws = deepcopy(list(registry.get("active_thaws") or []))
    matches = [item for item in thaws if item.get("thaw_id") == THAW_ID]
    if len(matches) != 1:
        raise RuntimeError("WNBA_DATA_STEP3_RETARGET_THAW_CARDINALITY")
    old_grant = matches[0]
    expected_old = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": OLD_CANDIDATE_SHA,
        "files": {PATH: {"from_blob": FROZEN_BLOB, "to_blob": OLD_TO_BLOB}},
    }
    if old_grant != expected_old:
        raise RuntimeError("WNBA_DATA_STEP3_RETARGET_OLD_GRANT_DRIFT")
    if any(PATH in (item.get("files") or {}) for item in thaws if item.get("thaw_id") != THAW_ID):
        raise RuntimeError("WNBA_DATA_STEP3_RETARGET_DUPLICATE_PATH")

    new_grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": NEW_CANDIDATE_SHA,
        "files": {PATH: {"from_blob": FROZEN_BLOB, "to_blob": NEW_BLOB}},
    }
    unrelated_before = [item for item in thaws if item.get("thaw_id") != THAW_ID]
    updated = deepcopy(registry)
    updated["active_thaws"] = [new_grant if item.get("thaw_id") == THAW_ID else item for item in thaws]
    updated["revision"] = int(registry["revision"]) + 1
    updated["source_main_sha"] = MAIN_SHA
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)

    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        REGISTRY_BRANCH,
        f"registry: retarget {THAW_ID}",
        str(raw["sha"]),
    )

    rb_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    rb = json.loads(base64.b64decode(rb_raw["content"]).decode())
    validate_registry(rb)
    rb_matches = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if rb_matches != [new_grant]:
        raise RuntimeError("WNBA_DATA_STEP3_RETARGET_READBACK_FAILED")
    unrelated_after = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    if unrelated_after != unrelated_before:
        raise RuntimeError("WNBA_DATA_STEP3_RETARGET_UNRELATED_DRIFT")

    return {
        "status": "GREEN",
        "old_candidate_sha": OLD_CANDIDATE_SHA,
        "candidate_sha": NEW_CANDIDATE_SHA,
        "thaw_id": THAW_ID,
        "registry_revision": int(rb["revision"]),
        "registry_state_hash": str(rb["state_hash"]),
        "owner_tokens": [token for token, _ in owners],
        "unrelated_thaws_preserved": len(unrelated_after),
        "main_mutated": False,
    }


def install_startup(app):
    app.state.wnba_data_step3_player_shell_retarget = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_data_step3_player_shell_retarget = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step3_player_shell_retarget = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print(
            "WNBA_DATA_STEP3_PLAYER_SHELL_RETARGET="
            + json.dumps(app.state.wnba_data_step3_player_shell_retarget, sort_keys=True),
            flush=True,
        )
    return app
