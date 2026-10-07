from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

MAIN_SHA = "4036459c8c8cde0ac8f3034b560d7948ad9a5015"
BRANCH = "runless-task17-step1-real-prove-execution-r1"
OLD_CANDIDATE_SHA = "97ac0eda464004c2debe45f84060b7830d2f8419"
NEW_CANDIDATE_SHA = "1f5b522861f8f9d3024b528f480d80f35e4e3902"
PATH = "runless_proof_plane/api.py"
FROM_BLOB = "185c07cb05fb5dc4937011330c6da6b7d5e8d1c5"
TO_BLOB = "3734146408aefba224f3ceed7c9385fc91eca68a"
THAW_ID = "THAW-RUNLESS-TASK17-STEP1-REAL-PROVE-R1"
EXPECTED_REVISION = 157
EXPECTED_HASH = "1a1bee408f285491f273502c73065554c30466ae95dd7cd65060098d10fcb30b"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("TASK17_STEP1_ROTATE_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != OLD_CANDIDATE_SHA:
        raise RuntimeError("TASK17_STEP1_ROTATE_BRANCH_DRIFT")
    new_commit = client.commit(NEW_CANDIDATE_SHA)
    if str(new_commit.get("sha") or "") != NEW_CANDIDATE_SHA:
        raise RuntimeError("TASK17_STEP1_ROTATE_NEW_CANDIDATE_MISSING")
    if str(client.tree_blobs(OLD_CANDIDATE_SHA).get(PATH) or "") != TO_BLOB:
        raise RuntimeError("TASK17_STEP1_ROTATE_OLD_BLOB_DRIFT")
    if str(client.tree_blobs(NEW_CANDIDATE_SHA).get(PATH) or "") != TO_BLOB:
        raise RuntimeError("TASK17_STEP1_ROTATE_NEW_BLOB_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("TASK17_STEP1_ROTATE_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise RuntimeError("TASK17_STEP1_ROTATE_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise RuntimeError("TASK17_STEP1_ROTATE_HASH_DRIFT")

    matches = [item for item in registry.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if len(matches) != 1:
        raise RuntimeError("TASK17_STEP1_ROTATE_THAW_IDENTITY_DRIFT")
    grant = matches[0]
    if str(grant.get("target_head_sha") or "") != OLD_CANDIDATE_SHA:
        raise RuntimeError("TASK17_STEP1_ROTATE_OLD_TARGET_DRIFT")
    pair = (grant.get("files") or {}).get(PATH) or {}
    if pair != {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}:
        raise RuntimeError("TASK17_STEP1_ROTATE_BLOB_PAIR_DRIFT")

    unrelated_before = [deepcopy(item) for item in registry.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    updated = deepcopy(registry)
    target = next(item for item in updated["active_thaws"] if item.get("thaw_id") == THAW_ID)
    target["target_head_sha"] = NEW_CANDIDATE_SHA
    updated["revision"] = int(registry["revision"]) + 1
    updated["source_main_sha"] = MAIN_SHA
    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)

    client.update_content(
        REGISTRY_PATH,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        REGISTRY_BRANCH,
        f"registry: rotate thaw {THAW_ID}",
        str(raw["sha"]),
    )

    rb_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    rb = json.loads(base64.b64decode(rb_raw["content"]).decode())
    validate_registry(rb)
    rb_matches = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if len(rb_matches) != 1 or rb_matches[0].get("target_head_sha") != NEW_CANDIDATE_SHA:
        raise RuntimeError("TASK17_STEP1_ROTATE_READBACK_FAILED")
    unrelated_after = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    if unrelated_after != unrelated_before:
        raise RuntimeError("TASK17_STEP1_ROTATE_UNRELATED_DRIFT")

    return {
        "status": "GREEN",
        "old_candidate_sha": OLD_CANDIDATE_SHA,
        "new_candidate_sha": NEW_CANDIDATE_SHA,
        "thaw_id": THAW_ID,
        "registry_revision": int(rb["revision"]),
        "registry_state_hash": str(rb["state_hash"]),
        "unrelated_thaws_preserved": len(unrelated_after),
    }


def install_startup(app):
    app.state.task17_step1_thaw_rotate = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step1_thaw_rotate = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step1_thaw_rotate = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:1000]
            }
        print(
            "RUNLESS_TASK17_STEP1_THAW_ROTATE="
            + json.dumps(app.state.task17_step1_thaw_rotate, sort_keys=True),
            flush=True,
        )
    return app
