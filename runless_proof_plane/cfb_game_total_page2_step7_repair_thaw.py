from __future__ import annotations

import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import validate_registry
from .registry import GithubRegistryBackend, _state_hash

MAIN_SHA = "c7bb9383c510c79dcca88f5e33d533a18085ee40"
TARGET_SHA = "f93e7364a3592224eec787ad7574fd94131945a6"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP7_LINE_LAB_BEST_BET_FROZEN"
THAW_ID = "THAW-CFB-GT-PAGE2-STEP7-REPAIR-R1"
FILES = {
    "cfb_game_total_page2_step7_line_lab_best_bet_v1.py": {
        "from_blob": "6cfdb7303062780415428df33780bbce31f8b3e5",
        "to_blob": "92b4467e7e45e5ba551a5734e162001bda26e725",
    },
    "tests/test_cfb_game_total_page2_step7_line_lab_best_bet_v1.py": {
        "from_blob": "2ee62ee7094670d33fe631a6408e3f0911d950fb",
        "to_blob": "3f4fe587aee08ca26f88ecba46ee2c010f6a56ab",
    },
}


def execute(app) -> dict:
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("STEP7_REPAIR_THAW_MAIN_DRIFT")
    tree = client.tree_blobs(TARGET_SHA)
    for path, pair in FILES.items():
        if tree.get(path) != pair["to_blob"]:
            raise RuntimeError(f"STEP7_REPAIR_THAW_TARGET_BLOB_DRIFT:{path}")

    backend = GithubRegistryBackend(client)
    before = backend.read_registry()
    entry = (before.get("entries") or {}).get(FREEZE_TOKEN)
    if not entry or entry.get("status") != "FROZEN":
        raise RuntimeError("STEP7_REPAIR_THAW_FREEZE_BASELINE_MISSING")
    if entry.get("source_main_sha") != MAIN_SHA:
        raise RuntimeError("STEP7_REPAIR_THAW_FREEZE_MAIN_DRIFT")
    for path, pair in FILES.items():
        if (entry.get("artifacts") or {}).get(path) != pair["from_blob"]:
            raise RuntimeError(f"STEP7_REPAIR_THAW_FROM_BLOB_DRIFT:{path}")

    expected_grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": TARGET_SHA,
        "files": deepcopy(FILES),
    }
    existing = next((g for g in before.get("active_thaws", []) if g.get("thaw_id") == THAW_ID), None)
    if existing is not None:
        if existing != expected_grant:
            raise RuntimeError("STEP7_REPAIR_THAW_ID_CONFLICT")
        after = before
    else:
        updated = deepcopy(before)
        updated["revision"] = int(before["revision"]) + 1
        updated["active_thaws"] = deepcopy(before.get("active_thaws", [])) + [expected_grant]
        updated["state_hash"] = _state_hash(updated)
        validate_registry(updated)
        if not backend._blob_sha:
            raise RuntimeError("STEP7_REPAIR_THAW_REGISTRY_BLOB_MISSING")
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
        raise RuntimeError("STEP7_REPAIR_THAW_READBACK_MISMATCH")
    return {
        "status": "GREEN",
        "decision": "EXACT_STEP7_REPAIR_THAW_GRANTED",
        "thaw_id": THAW_ID,
        "target_sha": TARGET_SHA,
        "file_count": len(FILES),
        "registry_revision": int(after["revision"]),
        "registry_hash": str(after["state_hash"]),
    }


def install_startup(app):
    app.state.cfb_game_total_page2_step7_repair_thaw = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:2400]}
        app.state.cfb_game_total_page2_step7_repair_thaw = result
        print("CFB_GT_PAGE2_STEP7_REPAIR_THAW=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    return app
