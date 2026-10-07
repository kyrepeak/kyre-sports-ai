from __future__ import annotations

import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry

from .receipts import GithubReceiptBackend, ReceiptStore
from .registry import GithubRegistryBackend, REGISTRY_PATH

PROOFED_MAIN_SHA = "d908cdc3e8ea4b0224333268e7b02d0af3bd9063"
PROOF_ID = "runless-task17-step1-real-prove-d908cdc3e8ea4b02-37bd09cab4008546"
RECEIPT_DIGEST = "f4faa7ae90982b13a7ccd97f66395ed251d033077df874ef8aa9888d8fcc84a6"
FREEZE_TOKEN = "RUNLESS_TASK17_STEP1_REAL_PROVE_FROZEN"
ARTIFACTS = {
    "devsystem/execution_plans/runless-task17-step1-real-prove-execution.json": "541eec687a39a0911d6f34191818d43585f29992",
    "devsystem/runless_proof_plans/runless-task17-step1-real-prove.json": "11288e4b57cb33ca1438e4c7827adfcad42b74fe",
    "devsystem/task_ledgers/runless-task17-step1-real-prove-execution.json": "5d9bd0d78a8de918c36241b39d1b3ccdd48b5d40",
    "runless_proof_plane/api.py": "3734146408aefba224f3ceed7c9385fc91eca68a",
    "runless_proof_plane/prove.py": "8ae595d75b369d4564bbe5fa746482626313c69d",
    "tests/test_runless_task17_step1_inherited_frozen_main.py": "d90bf68b57be15348407db43b36d75775bfb401a",
    "tests/test_runless_task17_step1_prove_runner.py": "e9a5053146dfcf490d57931c168ef26e3fd8614f",
    "tests/test_runless_task17_step1_real_prove.py": "872c7ee6d91a491cfc356c4db815e2db3a05b652",
}


class Task17FinalFreezeFailure(RuntimeError):
    pass


def _assert_ancestor(client, base_sha: str, head_sha: str) -> None:
    if base_sha == head_sha:
        return
    comparison = client.request("GET", f"/compare/{base_sha}...{head_sha}")
    if str(comparison.get("status") or "") != "ahead":
        raise Task17FinalFreezeFailure("PROOFED_MAIN_NOT_ANCESTOR_OF_CURRENT_MAIN")


def _assert_artifacts(client, sha: str) -> None:
    tree = client.tree_blobs(sha)
    drift = [path for path, blob in ARTIFACTS.items() if str(tree.get(path) or "").lower() != blob]
    if drift:
        raise Task17FinalFreezeFailure("STEP17_ARTIFACT_DRIFT:" + ",".join(sorted(drift)))


def execute(client):
    current_main = client.branch_sha("main")
    _assert_ancestor(client, PROOFED_MAIN_SHA, current_main)
    _assert_artifacts(client, PROOFED_MAIN_SHA)
    _assert_artifacts(client, current_main)

    receipt_store = ReceiptStore(GithubReceiptBackend(client, PROOFED_MAIN_SHA))
    receipt = receipt_store.get(PROOF_ID)
    if str(receipt.get("candidate_sha") or "") != PROOFED_MAIN_SHA:
        raise Task17FinalFreezeFailure("MERGED_MAIN_RECEIPT_CANDIDATE_DRIFT")
    if str(receipt.get("digest") or "") != RECEIPT_DIGEST:
        raise Task17FinalFreezeFailure("MERGED_MAIN_RECEIPT_DIGEST_DRIFT")
    if str(receipt.get("failure_class") or "") != "NONE":
        raise Task17FinalFreezeFailure("MERGED_MAIN_RECEIPT_NOT_GREEN")

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)

    source_main = str(registry.get("source_main_sha") or "")
    _assert_ancestor(client, PROOFED_MAIN_SHA, source_main)
    _assert_artifacts(client, source_main)

    existing = (registry.get("entries") or {}).get(FREEZE_TOKEN)
    exact_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": PROOFED_MAIN_SHA,
        "artifacts": dict(sorted(ARTIFACTS.items())),
    }
    if existing is not None:
        if existing != exact_entry:
            raise Task17FinalFreezeFailure("STEP17_FREEZE_TOKEN_COLLISION")
        return {
            "status": "GREEN",
            "decision": "RUNLESS_TASK17_STEP1_ALREADY_FROZEN",
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
            "artifact_count": len(ARTIFACTS),
            "current_main_sha": current_main,
        }

    active_before = deepcopy(registry.get("active_thaws", []))
    overlap = sorted(
        path
        for grant in active_before
        for path in (grant.get("files") or {})
        if path in ARTIFACTS
    )
    if overlap:
        raise Task17FinalFreezeFailure("STEP17_ARTIFACT_ACTIVE_THAW:" + ",".join(overlap))

    updated = deepcopy(registry)
    updated.setdefault("entries", {})[FREEZE_TOKEN] = exact_entry
    updated["revision"] = int(registry["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(_payload_without_hash(updated))
    validate_registry(updated)

    try:
        client.update_content(
            REGISTRY_PATH,
            json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            backend.branch,
            "registry: freeze Runless Task 17 Step 1 real prove execution",
            backend._blob_sha,
        )
    except Exception as exc:
        raise Task17FinalFreezeFailure("WAIT_REGISTRY_CAS_CONFLICT") from exc

    readback = backend.read_registry()
    validate_registry(readback)
    if int(readback["revision"]) != int(updated["revision"]):
        raise Task17FinalFreezeFailure("STEP17_FREEZE_READBACK_REVISION_MISMATCH")
    if str(readback.get("state_hash") or "") != str(updated["state_hash"]):
        raise Task17FinalFreezeFailure("STEP17_FREEZE_READBACK_HASH_MISMATCH")
    if readback.get("active_thaws", []) != active_before:
        raise Task17FinalFreezeFailure("STEP17_FREEZE_UNRELATED_THAW_DRIFT")
    if (readback.get("entries") or {}).get(FREEZE_TOKEN) != exact_entry:
        raise Task17FinalFreezeFailure("STEP17_FREEZE_ENTRY_READBACK_MISMATCH")

    return {
        "status": "GREEN",
        "decision": "RUNLESS_TASK17_STEP1_GREEN_FROZEN",
        "freeze_token": FREEZE_TOKEN,
        "proof_id": PROOF_ID,
        "receipt_digest": RECEIPT_DIGEST,
        "proofed_main_sha": PROOFED_MAIN_SHA,
        "current_main_sha": current_main,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "artifact_count": len(ARTIFACTS),
        "unrelated_thaws_preserved": len(active_before),
    }


def install_startup(app):
    app.state.task17_step1_final_freeze = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step1_final_freeze = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step1_final_freeze = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1600],
            }
        print(
            "RUNLESS_TASK17_STEP1_FINAL_FREEZE="
            + json.dumps(app.state.task17_step1_final_freeze, sort_keys=True),
            flush=True,
        )

    @app.get("/task17-step1-final-freeze/status")
    def _status():
        return app.state.task17_step1_final_freeze

    return app
