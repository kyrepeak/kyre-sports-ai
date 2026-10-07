from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

MAIN_SHA = "d908cdc3e8ea4b0224333268e7b02d0af3bd9063"
BRANCH = "runless-task17-step2-parallel-proof-slices-r1"
CANDIDATE_SHA = "34b8bc596ac8c34aa6f0506a20f27e1a20fad9f5"
PATH = "runless_proof_plane/executor.py"
FROZEN_BLOB = "0532db39d948587165bacb90f4a4fe4af762dd1e"
NEW_BLOB = "3bdbd770ddd3b4d62096f0b3bf72f25e9b38abdd"
THAW_ID = "THAW-RUNLESS-TASK17-STEP2-PARALLEL-PROOF-SLICES-R1"
EXPECTED_REVISION = 164
EXPECTED_HASH = "ef1e3a9dddaa8a724d90820b0c548e87473f5223b19fc6a6880c2e59014b550f"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("RUNLESS_TASK17_STEP2_THAW_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("RUNLESS_TASK17_STEP2_THAW_BRANCH_DRIFT")

    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if str(main_tree.get(PATH) or "") != FROZEN_BLOB:
        raise RuntimeError("RUNLESS_TASK17_STEP2_THAW_MAIN_BLOB_DRIFT")
    if str(candidate_tree.get(PATH) or "") != NEW_BLOB:
        raise RuntimeError("RUNLESS_TASK17_STEP2_THAW_CANDIDATE_BLOB_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("RUNLESS_TASK17_STEP2_THAW_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise RuntimeError("RUNLESS_TASK17_STEP2_THAW_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise RuntimeError("RUNLESS_TASK17_STEP2_THAW_HASH_DRIFT")

    owners = []
    for token, entry in (registry.get("entries") or {}).items():
        artifacts = entry.get("artifacts") or {}
        if PATH in artifacts:
            owners.append((str(token), str(artifacts[PATH])))
    if not owners or any(blob != FROZEN_BLOB for _, blob in owners):
        raise RuntimeError("RUNLESS_TASK17_STEP2_THAW_OWNER_DRIFT")

    thaws = deepcopy(list(registry.get("active_thaws") or []))
    if any(item.get("thaw_id") == THAW_ID for item in thaws):
        raise RuntimeError("RUNLESS_TASK17_STEP2_THAW_DUPLICATE_ID")
    if any(PATH in (item.get("files") or {}) for item in thaws):
        raise RuntimeError("RUNLESS_TASK17_STEP2_THAW_DUPLICATE_PATH")

    grant = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {PATH: {"from_blob": FROZEN_BLOB, "to_blob": NEW_BLOB}},
    }
    unrelated_before = deepcopy(thaws)
    updated = deepcopy(registry)
    updated["active_thaws"] = thaws + [grant]
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
        raise RuntimeError("RUNLESS_TASK17_STEP2_THAW_READBACK_FAILED")
    unrelated_after = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    if unrelated_after != unrelated_before:
        raise RuntimeError("RUNLESS_TASK17_STEP2_THAW_UNRELATED_DRIFT")

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
    app.state.task17_step2_parallel_thaw = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step2_parallel_thaw = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step2_parallel_thaw = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print(
            "RUNLESS_TASK17_STEP2_PARALLEL_THAW="
            + json.dumps(app.state.task17_step2_parallel_thaw, sort_keys=True),
            flush=True,
        )
    return app
