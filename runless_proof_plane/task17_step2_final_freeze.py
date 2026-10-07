from __future__ import annotations

import base64
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry

from .registry import GithubRegistryBackend, REGISTRY_PATH

MAIN_SHA = "51762ad9226b119626284655a90bd7ac7da80d5e"
FREEZE_TOKEN = "RUNLESS_TASK17_STEP2_PARALLEL_PROOF_SLICES_FROZEN"
PARENT_TOKEN = "RUNLESS_PROOF_PLANE_V1_TASK13"
THAW_ID = "THAW-RUNLESS-TASK17-STEP2-PARALLEL-PROOF-SLICES-R1"
EXPECTED_REVISION = 167
EXPECTED_REGISTRY_HASH = "19df7268cb1d8f636be4e5e0ced2e69a5887a72c60cc846dd6ab049772fd4bd0"
OLD_EXECUTOR_BLOB = "0532db39d948587165bacb90f4a4fe4af762dd1e"
NEW_EXECUTOR_BLOB = "3bdbd770ddd3b4d62096f0b3bf72f25e9b38abdd"
RECEIPT_REF = "runless-proof-receipts"
RECEIPTS = {
    "runless-task17-step2-parallel-proof-slices-34b8bc596ac8c34a-f98d36403bcee513": {
        "candidate_sha": "34b8bc596ac8c34aa6f0506a20f27e1a20fad9f5",
        "digest": "98c1729672c85ec4512db6e644184fa7a1eeb277fee8eb71065e3ea592674c5f",
    },
    "runless-task17-step2-parallel-proof-slices-51762ad9226b1196-44062d61db4423ee": {
        "candidate_sha": MAIN_SHA,
        "digest": "d29fbc8bc08665d8addc5d580bb15b87cf936aba60340981e9cf4c8cb7ea3f03",
    },
}
ARTIFACTS = {
    "devsystem/execution_plans/runless-task17-step2-parallel-proof-slices.json": "0531b0238a744a0fa494ef28957aa14ac62cabeb",
    "devsystem/runless_proof_plans/runless-task17-step2-parallel-proof-slices.json": "1a06e28b89836d7786528163c814b09a816d78ae",
    "devsystem/task_ledgers/runless-task17-step2-parallel-proof-slices.json": "9fb9f7e87c49d32a35c43706182fccd2ea337dcd",
    "runless_proof_plane/executor.py": NEW_EXECUTOR_BLOB,
    "tests/test_runless_task17_step2_parallel_slices.py": "349e2d1f8841c7690a79e789e993451f6e3d654a",
}


class Task17Step2FinalFreezeFailure(RuntimeError):
    pass


def _read_receipt(client, proof_id: str) -> dict:
    path = f"devsystem/runless_proof_receipts/{proof_id}.json"
    raw = client.content(path, ref=RECEIPT_REF)
    if not raw or raw.get("encoding") != "base64":
        raise Task17Step2FinalFreezeFailure("STEP2_RECEIPT_READ_FAILED:" + proof_id)
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise Task17Step2FinalFreezeFailure("STEP2_RECEIPT_DECODE_FAILED:" + proof_id) from exc


def _assert_receipts(client) -> None:
    for proof_id, expected in RECEIPTS.items():
        receipt = _read_receipt(client, proof_id)
        if str(receipt.get("proof_id") or "") != proof_id:
            raise Task17Step2FinalFreezeFailure("STEP2_RECEIPT_ID_DRIFT:" + proof_id)
        if str(receipt.get("candidate_sha") or "") != expected["candidate_sha"]:
            raise Task17Step2FinalFreezeFailure("STEP2_RECEIPT_CANDIDATE_DRIFT:" + proof_id)
        if str(receipt.get("digest") or "") != expected["digest"]:
            raise Task17Step2FinalFreezeFailure("STEP2_RECEIPT_DIGEST_DRIFT:" + proof_id)
        if str(receipt.get("failure_class") or "") != "NONE":
            raise Task17Step2FinalFreezeFailure("STEP2_RECEIPT_NOT_GREEN:" + proof_id)


def _assert_main_artifacts(client) -> None:
    if client.branch_sha("main") != MAIN_SHA:
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_MAIN_DRIFT")
    tree = client.tree_blobs(MAIN_SHA)
    drift = [path for path, blob in ARTIFACTS.items() if str(tree.get(path) or "").lower() != blob]
    if drift:
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_ARTIFACT_DRIFT:" + ",".join(sorted(drift)))


def execute(client):
    _assert_main_artifacts(client)
    _assert_receipts(client)

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_REGISTRY_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_REGISTRY_HASH_DRIFT")
    if str(registry.get("source_main_sha") or "") != MAIN_SHA:
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_REGISTRY_MAIN_DRIFT")

    entries = registry.get("entries") or {}
    parent = entries.get(PARENT_TOKEN)
    if not isinstance(parent, dict):
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_PARENT_MISSING")
    parent_artifacts = parent.get("artifacts") or {}
    if str(parent_artifacts.get("runless_proof_plane/executor.py") or "") != OLD_EXECUTOR_BLOB:
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_PARENT_EXECUTOR_DRIFT")

    thaws = deepcopy(list(registry.get("active_thaws") or []))
    matches = [item for item in thaws if item.get("thaw_id") == THAW_ID]
    if len(matches) != 1:
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_THAW_ID_DRIFT")
    grant = matches[0]
    if str(grant.get("target_head_sha") or "") != MAIN_SHA:
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_THAW_TARGET_DRIFT")
    pair = (grant.get("files") or {}).get("runless_proof_plane/executor.py") or {}
    if str(pair.get("from_blob") or "") != OLD_EXECUTOR_BLOB or str(pair.get("to_blob") or "") != NEW_EXECUTOR_BLOB:
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_THAW_BLOB_DRIFT")

    exact_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(sorted(ARTIFACTS.items())),
    }
    existing = entries.get(FREEZE_TOKEN)
    if existing is not None:
        if existing != exact_entry:
            raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_TOKEN_COLLISION")
        if any(item.get("thaw_id") == THAW_ID for item in thaws):
            raise Task17Step2FinalFreezeFailure("STEP2_ALREADY_FROZEN_BUT_THAW_ACTIVE")
        return {
            "status": "GREEN",
            "decision": "RUNLESS_TASK17_STEP2_ALREADY_GREEN_FROZEN",
            "freeze_token": FREEZE_TOKEN,
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
            "artifact_count": len(ARTIFACTS),
        }

    unrelated_before = [item for item in thaws if item.get("thaw_id") != THAW_ID]
    updated = deepcopy(registry)
    updated_parent = updated["entries"][PARENT_TOKEN]
    updated_parent_artifacts = dict(updated_parent["artifacts"])
    removed = updated_parent_artifacts.pop("runless_proof_plane/executor.py", None)
    if removed != OLD_EXECUTOR_BLOB:
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_PARENT_RELEASE_FAILED")
    updated_parent["artifacts"] = dict(sorted(updated_parent_artifacts.items()))
    updated["entries"][FREEZE_TOKEN] = exact_entry
    updated["active_thaws"] = unrelated_before
    updated["source_main_sha"] = MAIN_SHA
    updated["revision"] = int(registry["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(_payload_without_hash(updated))
    validate_registry(updated)

    try:
        client.update_content(
            REGISTRY_PATH,
            json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            backend.branch,
            "registry: freeze Runless Task 17 Step 2 parallel proof slices",
            backend._blob_sha,
        )
    except Exception as exc:
        raise Task17Step2FinalFreezeFailure("WAIT_REGISTRY_CAS_CONFLICT") from exc

    readback = backend.read_registry()
    validate_registry(readback)
    if int(readback["revision"]) != int(updated["revision"]):
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_READBACK_REVISION_MISMATCH")
    if str(readback.get("state_hash") or "") != str(updated["state_hash"]):
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_READBACK_HASH_MISMATCH")
    if readback.get("active_thaws", []) != unrelated_before:
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_UNRELATED_THAW_DRIFT")
    if (readback.get("entries") or {}).get(FREEZE_TOKEN) != exact_entry:
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_ENTRY_READBACK_MISMATCH")
    rb_parent = (readback.get("entries") or {}).get(PARENT_TOKEN) or {}
    if "runless_proof_plane/executor.py" in (rb_parent.get("artifacts") or {}):
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_PARENT_RELEASE_READBACK_FAILED")
    if client.branch_sha("main") != MAIN_SHA:
        raise Task17Step2FinalFreezeFailure("STEP2_FINAL_FREEZE_MAIN_MOVED_AFTER_WRITE")

    return {
        "status": "GREEN",
        "decision": "RUNLESS_TASK17_STEP2_GREEN_FROZEN",
        "freeze_token": FREEZE_TOKEN,
        "proofed_main_sha": MAIN_SHA,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "artifact_count": len(ARTIFACTS),
        "receipt_count": len(RECEIPTS),
        "parent_ownership_released": True,
        "step2_thaw_closed": True,
        "unrelated_thaws_preserved": len(unrelated_before),
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.task17_step2_final_freeze = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step2_final_freeze = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step2_final_freeze = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1600],
            }
        print(
            "RUNLESS_TASK17_STEP2_FINAL_FREEZE="
            + json.dumps(app.state.task17_step2_final_freeze, sort_keys=True),
            flush=True,
        )

    @app.get("/task17-step2-final-freeze/status")
    def _status():
        return app.state.task17_step2_final_freeze

    return app
