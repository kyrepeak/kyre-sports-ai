from __future__ import annotations

import base64
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt, validate_runless_receipt

from .gate import publish_gate
from .postmerge_reuse import evaluate_postmerge_reuse
from .registry import GithubRegistryBackend, REGISTRY_PATH

MAIN_SHA = "d2e2b45398e4a22c1e020a5fb5aca7b10e1debbb"
SOURCE_CANDIDATE_SHA = "87544f9ddced25a6c390709a4d3c039637a6e4b0"
LEASE_ID = "SCOPE-LEASE-C20C0E7167152850461F299C"
LEASE_OWNER = "monster-v2-runless-task17-step3"
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
EXPECTED_REGISTRY_REVISION = 170
EXPECTED_REGISTRY_HASH = "196b6fdebe580404ddeefa3ee5ac88a1584f00fec8e8d9223202c1aeb634f7ad"
FREEZE_TOKEN = "RUNLESS_TASK17_STEP3_POST_MERGE_PROOF_REUSE_FROZEN"
PREMERGE_PROOF_ID = "runless-task17-step3-post-merge-proof-reuse-87544f9ddced25a6-01f3a292ec2fbbba"
PREMERGE_DIGEST = "b1de5e93030fcac46a3fed5a8ff3a3c366d93df57ede3b9d228fedd1033db974"
PREMERGE_CHECK_ID = 112663693033
MERGED_PROOF_ID = "runless-task17-step3-post-merge-proof-reuse-d2e2b45398e4a22c-reused"
RECEIPT_REF = "runless-proof-receipts"
PLAN_PATH = "devsystem/runless_proof_plans/runless-task17-step3-post-merge-proof-reuse.json"
FREEZE_PATHS = (
    "devsystem/execution_plans/runless-task17-step3-post-merge-proof-reuse.json",
    "devsystem/runless_proof_plans/runless-task17-step3-post-merge-proof-reuse.json",
    "devsystem/task_ledgers/runless-task17-step3-post-merge-proof-reuse.json",
    "runless_proof_plane/postmerge_reuse.py",
    "tests/test_runless_task17_step3_postmerge_reuse.py",
)


class Task17Step3AtomicCloseoutFailure(RuntimeError):
    pass


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise Task17Step3AtomicCloseoutFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise Task17Step3AtomicCloseoutFailure(label + "_DECODE_FAILED") from exc


def _read_json(client, path: str, ref: str, label: str) -> dict:
    return _decode_json(client.content(path, ref=ref), label)


def _registry_summary(registry: dict) -> dict:
    return {
        "revision": int(registry["revision"]),
        "state_hash": str(registry["state_hash"]),
        "active_thaws": sorted(
            str(item.get("thaw_id") or "")
            for item in (registry.get("active_thaws") or [])
            if str(item.get("status") or "ACTIVE").upper() == "ACTIVE"
        ),
    }


def _assert_step2a(client) -> None:
    if client.branch_sha("main") != MAIN_SHA:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_MAIN_DRIFT")
    commit = client.commit(MAIN_SHA)
    parents = {str(item.get("sha") or "") for item in (commit.get("parents") or [])}
    if SOURCE_CANDIDATE_SHA not in parents:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_CANDIDATE_NOT_PARENT")

    lease = _read_json(client, LEASE_PATH, LEASE_REF, "STEP3_LEASE")
    holders = [item for item in (lease.get("holders") or []) if item.get("lease_id") == LEASE_ID]
    if len(holders) != 1:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_LEASE_ID_DRIFT")
    holder = holders[0]
    if str(holder.get("owner_id") or "") != LEASE_OWNER:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_LEASE_OWNER_DRIFT")
    identity = (holder.get("scope") or {}).get("resource_identity") or {}
    if str(identity.get("main_sha") or "") != MAIN_SHA:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_LEASE_MAIN_DRIFT")
    if str(identity.get("registry_state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_LEASE_REGISTRY_DRIFT")


def _load_premerge_receipt(client) -> dict:
    receipt = _read_json(
        client,
        f"devsystem/runless_proof_receipts/{PREMERGE_PROOF_ID}.json",
        RECEIPT_REF,
        "STEP3_PREMERGE_RECEIPT",
    )
    validate_runless_receipt(receipt)
    if str(receipt.get("proof_id") or "") != PREMERGE_PROOF_ID:
        raise Task17Step3AtomicCloseoutFailure("STEP3_PREMERGE_PROOF_ID_DRIFT")
    if str(receipt.get("candidate_sha") or "") != SOURCE_CANDIDATE_SHA:
        raise Task17Step3AtomicCloseoutFailure("STEP3_PREMERGE_CANDIDATE_DRIFT")
    if str(receipt.get("digest") or "") != PREMERGE_DIGEST:
        raise Task17Step3AtomicCloseoutFailure("STEP3_PREMERGE_DIGEST_DRIFT")
    if str(receipt.get("failure_class") or "") != "NONE":
        raise Task17Step3AtomicCloseoutFailure("STEP3_PREMERGE_NOT_GREEN")
    return receipt


def _ensure_merged_receipt(client, *, premerge: dict, registry: dict, tree: dict, reuse: dict) -> dict:
    path = f"devsystem/runless_proof_receipts/{MERGED_PROOF_ID}.json"
    existing = client.content(path, ref=RECEIPT_REF, allow_404=True)
    if existing:
        receipt = _decode_json(existing, "STEP3_MERGED_RECEIPT")
        validate_runless_receipt(receipt)
        if str(receipt.get("proof_id") or "") != MERGED_PROOF_ID:
            raise Task17Step3AtomicCloseoutFailure("STEP3_MERGED_RECEIPT_ID_DRIFT")
        if str(receipt.get("candidate_sha") or "") != MAIN_SHA:
            raise Task17Step3AtomicCloseoutFailure("STEP3_MERGED_RECEIPT_SHA_DRIFT")
        if str(receipt.get("prior_digest") or "") != PREMERGE_DIGEST:
            raise Task17Step3AtomicCloseoutFailure("STEP3_MERGED_RECEIPT_PRIOR_DRIFT")
        return receipt

    artifact_map = {path: str(tree.get(path) or "") for path in premerge["artifact_map"]}
    dependency_map = {path: str(tree.get(path) or "") for path in premerge["dependency_map"]}
    receipt = build_runless_receipt(
        proof_id=MERGED_PROOF_ID,
        task_id=str(premerge["task_id"]),
        project=str(premerge["project"]),
        workstream=str(premerge["workstream"]),
        step="task17-step3-postmerge-proof-reuse",
        candidate_sha=MAIN_SHA,
        artifact_map=artifact_map,
        dependency_map=dependency_map,
        registry_before=_registry_summary(registry),
        registry_after=_registry_summary(registry),
        evidence_digests=list(premerge.get("evidence_digests") or []),
        failure_class="NONE",
        prior_digest=PREMERGE_DIGEST,
        proof_fingerprint=str(premerge.get("proof_fingerprint") or ""),
        reused_from_proof_id=PREMERGE_PROOF_ID,
        reused_from_receipt_digest=PREMERGE_DIGEST,
        reuse_content_fingerprint=str(reuse.get("content_fingerprint") or ""),
        static_evidence_reexecuted=False,
        github_actions_enabled=False,
    )
    client.put_content(
        path,
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        RECEIPT_REF,
        "runless: persist Task 17 Step 3 merged-main reused receipt",
    )
    return receipt


def _ensure_gate(client, receipt: dict) -> bool:
    runs = client.request(
        "GET",
        f"/commits/{MAIN_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    expected_summary = "receipt=" + str(receipt["digest"])
    for run in runs.get("check_runs", []):
        output = run.get("output") or {}
        if (
            str(run.get("head_sha") or "") == MAIN_SHA
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
            and str(output.get("summary") or "") == expected_summary
        ):
            return False
    publish_gate(client, MAIN_SHA, "success", receipt)
    return True


def execute(client):
    _assert_step2a(client)
    premerge = _load_premerge_receipt(client)
    tree = client.tree_blobs(MAIN_SHA)

    merged_artifacts = {path: str(tree.get(path) or "") for path in premerge["artifact_map"]}
    merged_dependencies = {path: str(tree.get(path) or "") for path in premerge["dependency_map"]}
    if any(not value for value in merged_artifacts.values()):
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_ARTIFACT_MISSING")
    if any(not value for value in merged_dependencies.values()):
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_DEPENDENCY_MISSING")

    candidate_policy = _read_json(client, PLAN_PATH, SOURCE_CANDIDATE_SHA, "STEP3_CANDIDATE_POLICY")
    merged_policy = _read_json(client, PLAN_PATH, MAIN_SHA, "STEP3_MERGED_POLICY")
    reuse = evaluate_postmerge_reuse(
        premerge_receipt=premerge,
        merged_main_sha=MAIN_SHA,
        merged_artifacts=merged_artifacts,
        merged_dependencies=merged_dependencies,
        candidate_policy=candidate_policy,
        merged_policy=merged_policy,
        candidate_is_ancestor=True,
        proof_run_id=PREMERGE_CHECK_ID,
    )
    if reuse.get("decision") != "REUSE_APPROVED" or not reuse.get("reusable"):
        raise Task17Step3AtomicCloseoutFailure(
            "STEP3_CLOSEOUT_REUSE_REJECTED:" + ",".join(reuse.get("reasons") or [])
        )
    if reuse.get("static_evidence_reexecuted") is not False:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_STATIC_REEXECUTION_DETECTED")

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_REGISTRY_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_REGISTRY_HASH_DRIFT")
    if str(registry.get("source_main_sha") or "") != MAIN_SHA:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_REGISTRY_MAIN_DRIFT")

    freeze_artifacts = {path: str(tree.get(path) or "") for path in FREEZE_PATHS}
    if any(not value for value in freeze_artifacts.values()):
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_FREEZE_ARTIFACT_MISSING")
    exact_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(sorted(freeze_artifacts.items())),
    }

    merged_receipt = _ensure_merged_receipt(
        client,
        premerge=premerge,
        registry=registry,
        tree=tree,
        reuse=reuse,
    )
    gate_published = _ensure_gate(client, merged_receipt)

    entries = registry.get("entries") or {}
    existing = entries.get(FREEZE_TOKEN)
    if existing is not None:
        if existing != exact_entry:
            raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_FREEZE_TOKEN_COLLISION")
        return {
            "status": "GREEN",
            "decision": "RUNLESS_TASK17_STEP3_ALREADY_GREEN_FROZEN",
            "main_sha": MAIN_SHA,
            "freeze_token": FREEZE_TOKEN,
            "registry_revision": int(registry["revision"]),
            "registry_state_hash": str(registry["state_hash"]),
            "merged_receipt_digest": str(merged_receipt["digest"]),
            "gate_published": gate_published,
            "static_evidence_reexecuted": False,
            "github_actions_fallback": 0,
        }

    thaws_before = deepcopy(list(registry.get("active_thaws") or []))
    updated = deepcopy(registry)
    updated["entries"][FREEZE_TOKEN] = exact_entry
    updated["source_main_sha"] = MAIN_SHA
    updated["revision"] = int(registry["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(_payload_without_hash(updated))
    validate_registry(updated)

    if client.branch_sha("main") != MAIN_SHA:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_MAIN_MOVED_BEFORE_FREEZE")
    try:
        client.update_content(
            REGISTRY_PATH,
            json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            backend.branch,
            "registry: freeze Runless Task 17 Step 3 post-merge proof reuse",
            backend._blob_sha,
        )
    except Exception as exc:
        raise Task17Step3AtomicCloseoutFailure("WAIT_REGISTRY_CAS_CONFLICT") from exc

    readback = backend.read_registry()
    validate_registry(readback)
    if (readback.get("entries") or {}).get(FREEZE_TOKEN) != exact_entry:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_FREEZE_READBACK_MISMATCH")
    if readback.get("active_thaws", []) != thaws_before:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_UNRELATED_THAW_DRIFT")
    if str(readback.get("source_main_sha") or "") != MAIN_SHA:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_READBACK_MAIN_DRIFT")
    if client.branch_sha("main") != MAIN_SHA:
        raise Task17Step3AtomicCloseoutFailure("STEP3_CLOSEOUT_MAIN_MOVED_AFTER_FREEZE")

    return {
        "status": "GREEN",
        "decision": "RUNLESS_TASK17_STEP3_GREEN_FROZEN",
        "main_sha": MAIN_SHA,
        "source_candidate_sha": SOURCE_CANDIDATE_SHA,
        "freeze_token": FREEZE_TOKEN,
        "registry_revision": int(readback["revision"]),
        "registry_state_hash": str(readback["state_hash"]),
        "artifact_count": len(freeze_artifacts),
        "premerge_receipt_digest": PREMERGE_DIGEST,
        "merged_receipt_digest": str(merged_receipt["digest"]),
        "reuse_content_fingerprint": str(reuse.get("content_fingerprint") or ""),
        "gate_published": gate_published,
        "static_evidence_reexecuted": False,
        "unrelated_thaws_preserved": len(thaws_before),
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.task17_step3_atomic_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step3_atomic_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step3_atomic_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "RUNLESS_TASK17_STEP3_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.task17_step3_atomic_closeout, sort_keys=True),
            flush=True,
        )

    return app
