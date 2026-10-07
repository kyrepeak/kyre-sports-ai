from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry

MAIN_SHA = "4036459c8c8cde0ac8f3034b560d7948ad9a5015"
BRANCH = "runless-task17-step1-real-prove-execution-r1"
PARKED_BRANCH_SHA = "3c03397037290f0d49875f4f47db7f0c3fe79ce3"
CANDIDATE_SHA = "97ac0eda464004c2debe45f84060b7830d2f8419"
PATH = "runless_proof_plane/api.py"
FROM_BLOB = "185c07cb05fb5dc4937011330c6da6b7d5e8d1c5"
TO_BLOB = "3734146408aefba224f3ceed7c9385fc91eca68a"
OWNER_TOKEN = "RUNLESS_PROOF_PLANE_V1_TASK13"
THAW_ID = "THAW-RUNLESS-TASK17-STEP1-REAL-PROVE-R1"
EXPECTED_REVISION = 156
EXPECTED_HASH = "4c41f30b1440ddeac8d549191f54717a09b7507af272c00c44d4ada8ada31852"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")


def _state_hash(payload):
    value = deepcopy(dict(payload))
    value.pop("state_hash", None)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("TASK17_STEP1_THAW_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != PARKED_BRANCH_SHA:
        raise RuntimeError("TASK17_STEP1_THAW_PARKED_BRANCH_DRIFT")

    candidate = client.commit(CANDIDATE_SHA)
    if str(candidate.get("sha") or "") != CANDIDATE_SHA:
        raise RuntimeError("TASK17_STEP1_THAW_CANDIDATE_MISSING")

    main_tree = client.tree_blobs(MAIN_SHA)
    parked_tree = client.tree_blobs(PARKED_BRANCH_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if str(main_tree.get(PATH) or "") != FROM_BLOB:
        raise RuntimeError("TASK17_STEP1_THAW_MAIN_BLOB_DRIFT")
    if str(parked_tree.get(PATH) or "") != FROM_BLOB:
        raise RuntimeError("TASK17_STEP1_THAW_PARKED_BLOB_DRIFT")
    if str(candidate_tree.get(PATH) or "") != TO_BLOB:
        raise RuntimeError("TASK17_STEP1_THAW_CANDIDATE_BLOB_DRIFT")

    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("TASK17_STEP1_THAW_REGISTRY_READ_FAILED")
    registry = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise RuntimeError("TASK17_STEP1_THAW_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise RuntimeError("TASK17_STEP1_THAW_HASH_DRIFT")

    owner = ((registry.get("entries") or {}).get(OWNER_TOKEN) or {}).get("artifacts") or {}
    if str(owner.get(PATH) or "") != FROM_BLOB:
        raise RuntimeError("TASK17_STEP1_THAW_OWNER_BASELINE_DRIFT")

    thaws = deepcopy(list(registry.get("active_thaws") or []))
    if any(PATH in (item.get("files") or {}) for item in thaws):
        raise RuntimeError("TASK17_STEP1_THAW_PATH_ALREADY_ACTIVE")
    if any(item.get("thaw_id") == THAW_ID for item in thaws):
        raise RuntimeError("TASK17_STEP1_THAW_ID_EXISTS")

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
        raise RuntimeError("TASK17_STEP1_THAW_READBACK_FAILED")
    unrelated_after = [item for item in rb.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
    if unrelated_after != thaws:
        raise RuntimeError("TASK17_STEP1_THAW_UNRELATED_DRIFT")

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
    app.state.task17_step1_thaw = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step1_thaw = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step1_thaw = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print(
            "RUNLESS_TASK17_STEP1_THAW="
            + json.dumps(app.state.task17_step1_thaw, sort_keys=True),
            flush=True,
        )
    return app
