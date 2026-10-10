from __future__ import annotations

import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import validate_registry
from .registry import GithubRegistryBackend, _state_hash

MAIN_SHA = "c7bb9383c510c79dcca88f5e33d533a18085ee40"
TARGET_SHA = "2743ec3197d881279260d2ab407d0bb2f49d2ed2"
THAW_ID = "THAW-CFB-GT-PAGE2-STEP8-APP-R1"
FILES = {
    "app.py": {
        "from_blob": "b649282cd6fc771c6621cc09a655414f9422791a",
        "to_blob": "426a53efd90b6e15149f78d1cb61acfb1e1195c3",
    },
}


def execute(app) -> dict:
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("STEP8_APP_THAW_MAIN_DRIFT")
    main_tree = client.tree_blobs(MAIN_SHA)
    target_tree = client.tree_blobs(TARGET_SHA)
    for path, pair in FILES.items():
        if main_tree.get(path) != pair["from_blob"]:
            raise RuntimeError(f"STEP8_APP_THAW_FROM_BLOB_DRIFT:{path}")
        if target_tree.get(path) != pair["to_blob"]:
            raise RuntimeError(f"STEP8_APP_THAW_TARGET_BLOB_DRIFT:{path}")

    backend = GithubRegistryBackend(client)
    before = backend.read_registry()
    expected_grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": TARGET_SHA,
        "files": deepcopy(FILES),
    }
    existing = next((g for g in before.get("active_thaws", []) if g.get("thaw_id") == THAW_ID), None)
    if existing is not None:
        if existing != expected_grant:
            raise RuntimeError("STEP8_APP_THAW_ID_CONFLICT")
        after = before
    else:
        updated = deepcopy(before)
        updated["revision"] = int(before["revision"]) + 1
        updated["active_thaws"] = deepcopy(before.get("active_thaws", [])) + [expected_grant]
        updated["state_hash"] = _state_hash(updated)
        validate_registry(updated)
        if not backend._blob_sha:
            raise RuntimeError("STEP8_APP_THAW_REGISTRY_BLOB_MISSING")
        client.update_content(
            backend.path,
            json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            backend.branch,
            f"registry: grant {THAW_ID}",
            backend._blob_sha,
        )
        after = backend.read_registry()

    grant = next((g for g in after.get("active_thaws", []) if g.get("thaw_id") == THAW_ID), None)
    if grant != expected_grant:
        raise RuntimeError("STEP8_APP_THAW_READBACK_MISMATCH")
    return {
        "status": "GREEN",
        "decision": "EXACT_STEP8_APP_THAW_GRANTED",
        "thaw_id": THAW_ID,
        "target_sha": TARGET_SHA,
        "file_count": len(FILES),
        "registry_revision": int(after["revision"]),
        "registry_hash": str(after["state_hash"]),
    }


def install_startup(app):
    app.state.cfb_game_total_page2_step8_app_thaw = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:2400]}
        app.state.cfb_game_total_page2_step8_app_thaw = result
        print("CFB_GT_PAGE2_STEP8_APP_THAW=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    return app
