from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone

from devsystem.frozen_artifact_registry_v1 import validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt, validate_runless_receipt
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state

from .gate import publish_gate
from .postmerge_reuse import evaluate_postmerge_reuse
from .receipts import GithubReceiptBackend, ReceiptStore
from .registry import GithubRegistryBackend

TASK_ID = "runless-task17-step3-post-merge-proof-reuse"
WORKSTREAM = "runless-task17-step3"
PLAN_PATH = "devsystem/runless_proof_plans/runless-task17-step3-post-merge-proof-reuse.json"
CANDIDATE_SHA = "87544f9ddced25a6c390709a4d3c039637a6e4b0"
MERGED_MAIN_SHA = "d2e2b45398e4a22c1e020a5fb5aca7b10e1debbb"
PREMERGE_PROOF_ID = "runless-task17-step3-post-merge-proof-reuse-87544f9ddced25a6-01f3a292ec2fbbba"
PREMERGE_RECEIPT_DIGEST = "b1de5e93030fcac46a3fed5a8ff3a3c366d93df57ede3b9d228fedd1033db974"
PREMERGE_CHECK_ID = 112663693033
MERGED_PROOF_ID = "runless-task17-step3-postmerge-reuse-d2e2b45398e4a22c-reused-b1de5e93030fcac4"
LEASE_ID = "SCOPE-LEASE-C20C0E7167152850461F299C"
LEASE_OWNER = "monster-v2-runless-task17-step3"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
REGISTRY_REVISION = 170
REGISTRY_HASH = "196b6fdebe580404ddeefa3ee5ac88a1584f00fec8e8d9223202c1aeb634f7ad"
RECEIPT_REF = "runless-proof-receipts"
RECEIPT_BASE = "devsystem/runless_proof_receipts"


class Task17Step3MergedReuseFailure(RuntimeError):
    pass


def _decode(raw, error: str):
    if not raw or raw.get("encoding") != "base64":
        raise Task17Step3MergedReuseFailure(error)
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise Task17Step3MergedReuseFailure(error) from exc


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _policy(plan: dict) -> dict:
    return {
        "task_id": str(plan.get("task_id") or ""),
        "workstream": str(plan.get("workstream") or ""),
        "commands": list(plan.get("commands") or []),
        "probes": list(plan.get("probes") or []),
        "timeout_seconds": int(plan.get("timeout_seconds") or 0),
        "live_ttl_seconds": int(plan.get("live_ttl_seconds") or 0),
        "freeze_token": str(plan.get("freeze_token") or ""),
    }


def _path_map(tree: dict[str, str], paths: list[str], label: str) -> dict[str, str]:
    missing = [path for path in paths if path not in tree]
    if missing:
        raise Task17Step3MergedReuseFailure(f"STEP3_REUSE_{label}_MISSING:" + ",".join(sorted(missing)))
    return {path: str(tree[path]).lower() for path in sorted(paths)}


def _verify_step2a(client):
    if client.branch_sha("main") != MERGED_MAIN_SHA:
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_MAIN_DRIFT")

    registry = GithubRegistryBackend(client).read_registry()
    validate_registry(registry)
    if int(registry.get("revision") or -1) != REGISTRY_REVISION:
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_REGISTRY_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != REGISTRY_HASH:
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_REGISTRY_HASH_DRIFT")
    if str(registry.get("source_main_sha") or "") != MERGED_MAIN_SHA:
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_REGISTRY_MAIN_DRIFT")

    lease = validate_scope_lease_state(
        _decode(client.content(LEASE_PATH, ref=LEASE_BRANCH), "STEP3_REUSE_LEASE_READ_FAILED")
    )
    now = datetime.now(timezone.utc)
    matches = []
    for holder in lease.get("holders", []):
        if holder.get("lease_id") != LEASE_ID or holder.get("owner_id") != LEASE_OWNER:
            continue
        expiry = datetime.fromisoformat(str(holder.get("expires_at_utc") or "").replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if now >= expiry.astimezone(timezone.utc):
            continue
        scope = holder.get("scope") or {}
        identity = scope.get("resource_identity") or {}
        if identity.get("main_sha") != MERGED_MAIN_SHA:
            continue
        if identity.get("registry_state_hash") != REGISTRY_HASH:
            continue
        matches.append(holder)
    if len(matches) != 1:
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_SCOPE_LEASE_IDENTITY_DRIFT")
    return registry


def execute(app):
    client = app.state.github_client
    registry = _verify_step2a(client)

    merged_commit = client.commit(MERGED_MAIN_SHA)
    parents = {str(item.get("sha") or "") for item in (merged_commit.get("parents") or [])}
    candidate_is_ancestor = CANDIDATE_SHA in parents
    if not candidate_is_ancestor:
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_CANDIDATE_NOT_PARENT")

    premerge = _decode(
        client.content(f"{RECEIPT_BASE}/{PREMERGE_PROOF_ID}.json", ref=RECEIPT_REF),
        "STEP3_REUSE_PREMERGE_RECEIPT_READ_FAILED",
    )
    validate_runless_receipt(premerge)
    if premerge.get("proof_id") != PREMERGE_PROOF_ID:
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_PREMERGE_PROOF_ID_DRIFT")
    if premerge.get("candidate_sha") != CANDIDATE_SHA:
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_PREMERGE_CANDIDATE_DRIFT")
    if premerge.get("digest") != PREMERGE_RECEIPT_DIGEST:
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_PREMERGE_DIGEST_DRIFT")
    if str(premerge.get("failure_class") or "") != "NONE":
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_PREMERGE_NOT_GREEN")

    candidate_plan = _decode(client.content(PLAN_PATH, ref=CANDIDATE_SHA), "STEP3_REUSE_CANDIDATE_PLAN_READ_FAILED")
    merged_plan = _decode(client.content(PLAN_PATH, ref=MERGED_MAIN_SHA), "STEP3_REUSE_MERGED_PLAN_READ_FAILED")
    if candidate_plan.get("task_id") != TASK_ID or merged_plan.get("task_id") != TASK_ID:
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_TASK_ID_DRIFT")
    if candidate_plan.get("workstream") != WORKSTREAM or merged_plan.get("workstream") != WORKSTREAM:
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_WORKSTREAM_DRIFT")

    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    merged_tree = client.tree_blobs(MERGED_MAIN_SHA)
    artifact_paths = list(candidate_plan.get("artifacts") or [])
    dependency_paths = list(candidate_plan.get("dependencies") or [])
    candidate_artifacts = _path_map(candidate_tree, artifact_paths, "CANDIDATE_ARTIFACT")
    candidate_dependencies = _path_map(candidate_tree, dependency_paths, "CANDIDATE_DEPENDENCY")
    merged_artifacts = _path_map(merged_tree, artifact_paths, "MERGED_ARTIFACT")
    merged_dependencies = _path_map(merged_tree, dependency_paths, "MERGED_DEPENDENCY")
    if candidate_artifacts != dict(premerge.get("artifact_map") or {}):
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_PREMERGE_ARTIFACT_RECEIPT_DRIFT")
    if candidate_dependencies != dict(premerge.get("dependency_map") or {}):
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_PREMERGE_DEPENDENCY_RECEIPT_DRIFT")

    reuse = evaluate_postmerge_reuse(
        premerge_receipt=premerge,
        merged_main_sha=MERGED_MAIN_SHA,
        merged_artifacts=merged_artifacts,
        merged_dependencies=merged_dependencies,
        candidate_policy=_policy(candidate_plan),
        merged_policy=_policy(merged_plan),
        candidate_is_ancestor=candidate_is_ancestor,
        proof_run_id=PREMERGE_CHECK_ID,
    )
    if reuse.get("decision") != "REUSE_APPROVED" or reuse.get("reusable") is not True:
        raise Task17Step3MergedReuseFailure(
            "STEP3_REUSE_NOT_APPROVED:" + ",".join(reuse.get("reasons") or [])
        )
    if reuse.get("static_evidence_reexecuted") is not False:
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_STATIC_EVIDENCE_RERUN")
    if reuse.get("github_actions_enabled") is not False:
        raise Task17Step3MergedReuseFailure("STEP3_REUSE_ACTIONS_FALLBACK_ENABLED")

    registry_receipt = {
        "revision": int(registry["revision"]),
        "state_hash": str(registry["state_hash"]),
        "active_thaws": [str(item["thaw_id"]) for item in registry.get("active_thaws", [])],
    }
    reuse_digest = _digest(reuse)
    merged_receipt = build_runless_receipt(
        proof_id=MERGED_PROOF_ID,
        task_id=TASK_ID,
        project="API2",
        workstream=WORKSTREAM,
        step="task17-step3-post-merge-proof-reuse",
        candidate_sha=MERGED_MAIN_SHA,
        artifact_map=merged_artifacts,
        dependency_map=merged_dependencies,
        registry_before=registry_receipt,
        registry_after=registry_receipt,
        evidence_digests=[reuse_digest],
        failure_class="NONE",
        deployment_identity=app.state.settings.deployment_identity,
        proof_fingerprint=str(reuse["content_fingerprint"]),
        prior_digest=PREMERGE_RECEIPT_DIGEST,
        prior_proof_id=PREMERGE_PROOF_ID,
        reuse_decision=reuse,
        static_evidence_reexecuted=False,
        github_actions_enabled=False,
        reused_from_candidate_sha=CANDIDATE_SHA,
        reused_from_receipt_digest=PREMERGE_RECEIPT_DIGEST,
    )

    store = ReceiptStore(
        GithubReceiptBackend(
            client,
            MERGED_MAIN_SHA,
            app.state.settings.receipt_ref,
            app.state.settings.receipt_path,
        ),
        app.state.settings.receipt_ref,
        app.state.settings.receipt_path,
    )
    receipt_path = f"{store.base_path}/{MERGED_PROOF_ID}.json"
    if store.backend.exists(receipt_path, store.ref):
        existing = store.get(MERGED_PROOF_ID)
        if existing.get("digest") != merged_receipt.get("digest"):
            raise Task17Step3MergedReuseFailure("STEP3_REUSE_MERGED_RECEIPT_COLLISION")
        merged_receipt = existing
    else:
        store.put(merged_receipt)

    publish_gate(
        client,
        MERGED_MAIN_SHA,
        "success",
        merged_receipt,
        app.state.settings.gate_name,
    )

    return {
        "status": "GREEN",
        "decision": "RUNLESS_TASK17_STEP3_MERGED_REUSE_APPROVED",
        "merged_main_sha": MERGED_MAIN_SHA,
        "source_candidate_sha": CANDIDATE_SHA,
        "premerge_proof_id": PREMERGE_PROOF_ID,
        "premerge_receipt_digest": PREMERGE_RECEIPT_DIGEST,
        "merged_proof_id": MERGED_PROOF_ID,
        "merged_receipt_digest": merged_receipt["digest"],
        "reuse_content_fingerprint": reuse["content_fingerprint"],
        "reuse_evidence_digest": reuse_digest,
        "artifact_count": len(merged_artifacts),
        "dependency_count": len(merged_dependencies),
        "static_evidence_reexecuted": False,
        "github_actions_enabled": False,
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
    }


def install_startup(app):
    app.state.task17_step3_merged_reuse = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step3_merged_reuse = execute(app)
        except Exception as exc:
            app.state.task17_step3_merged_reuse = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1600],
            }
        print(
            "RUNLESS_TASK17_STEP3_MERGED_REUSE="
            + json.dumps(app.state.task17_step3_merged_reuse, sort_keys=True),
            flush=True,
        )

    return app
