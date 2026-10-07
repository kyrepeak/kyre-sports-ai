from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

OLD_MAIN_SHA = "d908cdc3e8ea4b0224333268e7b02d0af3bd9063"
MERGED_MAIN_SHA = "51762ad9226b119626284655a90bd7ac7da80d5e"
CANDIDATE_SHA = "34b8bc596ac8c34aa6f0506a20f27e1a20fad9f5"
PATH = "runless_proof_plane/executor.py"
OLD_BLOB = "0532db39d948587165bacb90f4a4fe4af762dd1e"
NEW_BLOB = "3bdbd770ddd3b4d62096f0b3bf72f25e9b38abdd"
THAW_ID = "THAW-RUNLESS-TASK17-STEP2-PARALLEL-PROOF-SLICES-R1"
EXPECTED_REVISION = 165
EXPECTED_HASH = "a0e0c63e222805fba546bcdcce73b96447a77d1af6c25f40aeef82d49284cc0a"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")
STEP2_PATHS = (
    "runless_proof_plane/executor.py",
    "tests/test_runless_task17_step2_parallel_slices.py",
    "devsystem/runless_proof_plans/runless-task17-step2-parallel-proof-slices.json",
    "devsystem/execution_plans/runless-task17-step2-parallel-proof-slices.json",
    "devsystem/task_ledgers/runless-task17-step2-parallel-proof-slices.json",
)


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def execute(client):
    if client.branch_sha("main") != MERGED_MAIN_SHA:
        raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_MAIN_DRIFT")
    merged_tree = client.tree_blobs(MERGED_MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if str(merged_tree.get(PATH) or "") != NEW_BLOB:
        raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_EXECUTOR_DRIFT")
    for path in STEP2_PATHS:
        if not merged_tree.get(path):
            raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_MISSING:" + path)
        if merged_tree.get(path) != candidate_tree.get(path):
            raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_CANDIDATE_MISMATCH:" + path)

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_HASH_DRIFT")
    if str(registry.get("source_main_sha") or "") != OLD_MAIN_SHA:
        raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_SOURCE_MAIN_DRIFT")

    thaws = deepcopy(list(registry.get("active_thaws") or []))
    matches = [item for item in thaws if item.get("thaw_id") == THAW_ID]
    if len(matches) != 1:
        raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_THAW_ID_DRIFT")
    grant = matches[0]
    if str(grant.get("target_head_sha") or "") != CANDIDATE_SHA:
        raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_THAW_TARGET_DRIFT")
    pair = (grant.get("files") or {}).get(PATH) or {}
    if str(pair.get("from_blob") or "") != OLD_BLOB or str(pair.get("to_blob") or "") != NEW_BLOB:
        raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_THAW_BLOB_DRIFT")

    unrelated_before = deepcopy([item for item in thaws if item.get("thaw_id") != THAW_ID])
    updated = deepcopy(registry)
    updated_grants = deepcopy(thaws)
    for item in updated_grants:
        if item.get("thaw_id") == THAW_ID:
            item["target_head_sha"] = MERGED_MAIN_SHA
    updated["active_thaws"] = updated_grants
    updated["source_main_sha"] = MERGED_MAIN_SHA
    updated["revision"] = int(registry["revision"]) + 1
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)

    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        REGISTRY_BRANCH,
        f"registry: retarget {THAW_ID} to merged main",
        str(raw["sha"]),
    )

    rb_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    rb = json.loads(base64.b64decode(rb_raw["content"]).decode())
    validate_registry(rb)
    rb_matches = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if len(rb_matches) != 1 or rb_matches[0].get("target_head_sha") != MERGED_MAIN_SHA:
        raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_THAW_READBACK_FAILED")
    unrelated_after = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    if unrelated_after != unrelated_before:
        raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_UNRELATED_DRIFT")
    if rb.get("source_main_sha") != MERGED_MAIN_SHA:
        raise RuntimeError("RUNLESS_TASK17_STEP2_POSTMERGE_MAIN_READBACK_FAILED")

    return {
        "status": "GREEN",
        "merged_main_sha": MERGED_MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "thaw_id": THAW_ID,
        "registry_revision": int(rb["revision"]),
        "registry_state_hash": str(rb["state_hash"]),
        "unrelated_thaws_preserved": len(unrelated_after),
        "step2_paths_exact": len(STEP2_PATHS),
    }


def install_startup(app):
    app.state.task17_step2_postmerge_retarget = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step2_postmerge_retarget = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step2_postmerge_retarget = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:1000]
            }
        print(
            "RUNLESS_TASK17_STEP2_POSTMERGE_RETARGET="
            + json.dumps(app.state.task17_step2_postmerge_retarget, sort_keys=True),
            flush=True,
        )
    return app
