from __future__ import annotations

import base64
import json
from copy import deepcopy

from devsystem.event_driven_resume_v1 import validate_state as validate_event_resume_state
from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt, validate_runless_receipt
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state

from .gate import publish_gate
from .postmerge_reuse import evaluate_postmerge_reuse
from .registry import GithubRegistryBackend, REGISTRY_PATH

TASK_ID = "runless-task17-step4-event-driven-resume"
WORKSTREAM = "runless-task17-step4"
PLAN_PATH = "devsystem/runless_proof_plans/runless-task17-step4-event-driven-resume.json"
SOURCE_MAIN_SHA = "7e8dfad79fb2745439ae1985de4d392b4e90f451"
SOURCE_CANDIDATE_SHA = "dc75208f04ed7daa6e8d6a87154fed9026e0a942"
MAIN_SHA = "0f54693bea39146747b98cbb7d15c0a4c778f0c8"
PREMERGE_PROOF_ID = "runless-task17-step4-event-driven-resume-dc75208f04ed7daa-cac4a5b3411a80e6"
PREMERGE_DIGEST = "3ef058dfc4891674ac0bc605b72f9738b84d75252a5238e5dcc760f0296eadea"
PREMERGE_CHECK_ID = 112673506171
MERGED_PROOF_ID = "runless-task17-step4-event-driven-resume-0f54693bea391467-reused"
FREEZE_TOKEN = "RUNLESS_TASK17_STEP4_EVENT_DRIVEN_RESUME_FROZEN"
FREEZE_PATHS = (
    "devsystem/execution_plans/runless-task17-step4-event-driven-resume.json",
    "devsystem/runless_proof_plans/runless-task17-step4-event-driven-resume.json",
    "devsystem/task_ledgers/runless-task17-step4-event-driven-resume.json",
    "runless_proof_plane/event_resume.py",
    "tests/test_runless_task17_step4_event_driven_resume.py",
)
LEASE_ID = "SCOPE-LEASE-C20C0E7167152850461F299C"
LEASE_OWNER = "monster-v2-runless-task17-step4"
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
EXPECTED_REGISTRY_REVISION = 173
EXPECTED_REGISTRY_HASH = "af27f2d2395fcb4bc240b0c52a6b6dfdc863d5dc0b7fe6b3bafb3a0417dfa322"
EVENT_REF = "monster-event-driven-resume"
EVENT_PATH = "devsystem/event_driven_resume_state_v1.json"
EXPECTED_EVENT_HASH = "6127af782bb3bdf62793e077d4ed5282b2fce5df7324860ee1f224d595e1f789"
RECEIPT_REF = "runless-proof-receipts"
RECEIPT_BASE = "devsystem/runless_proof_receipts"


class Task17Step4AtomicCloseoutFailure(RuntimeError):
    pass


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise Task17Step4AtomicCloseoutFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise Task17Step4AtomicCloseoutFailure(label + "_DECODE_FAILED") from exc


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


def _assert_step2a(client) -> tuple[dict, dict, dict]:
    if client.branch_sha("main") != MAIN_SHA:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_MAIN_DRIFT")
    commit = client.commit(MAIN_SHA)
    parents = {str(item.get("sha") or "") for item in (commit.get("parents") or [])}
    if SOURCE_MAIN_SHA not in parents or SOURCE_CANDIDATE_SHA not in parents:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_MERGE_LINEAGE_DRIFT")

    lease = validate_scope_lease_state(_read_json(client, LEASE_PATH, LEASE_REF, "STEP4_LEASE"))
    holders = [
        item for item in (lease.get("holders") or [])
        if item.get("lease_id") == LEASE_ID and item.get("owner_id") == LEASE_OWNER
    ]
    if len(holders) != 1:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_LEASE_IDENTITY_DRIFT")
    identity = (holders[0].get("scope") or {}).get("resource_identity") or {}
    if str(identity.get("main_sha") or "") != MAIN_SHA:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_LEASE_MAIN_DRIFT")
    if str(identity.get("registry_state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_LEASE_REGISTRY_DRIFT")
    if str(identity.get("event_resume_state_hash") or "") != EXPECTED_EVENT_HASH:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_LEASE_EVENT_STATE_DRIFT")

    event_state = validate_event_resume_state(_read_json(client, EVENT_PATH, EVENT_REF, "STEP4_EVENT_STATE"))
    if str(event_state.get("state_hash") or "") != EXPECTED_EVENT_HASH:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_EVENT_STATE_DRIFT")

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validated = validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_REGISTRY_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_REGISTRY_HASH_DRIFT")
    if str(registry.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_REGISTRY_SOURCE_MAIN_DRIFT")

    old_tree = client.tree_blobs(SOURCE_MAIN_SHA)
    merged_tree = client.tree_blobs(MAIN_SHA)
    for path in sorted(validated["artifacts"]):
        if str(old_tree.get(path) or "") != str(merged_tree.get(path) or ""):
            raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_EXISTING_FROZEN_DELTA:" + path)
    return registry, event_state, merged_tree


def _load_premerge_receipt(client) -> dict:
    receipt = _read_json(
        client,
        f"{RECEIPT_BASE}/{PREMERGE_PROOF_ID}.json",
        RECEIPT_REF,
        "STEP4_PREMERGE_RECEIPT",
    )
    validate_runless_receipt(receipt)
    if str(receipt.get("proof_id") or "") != PREMERGE_PROOF_ID:
        raise Task17Step4AtomicCloseoutFailure("STEP4_PREMERGE_PROOF_ID_DRIFT")
    if str(receipt.get("candidate_sha") or "") != SOURCE_CANDIDATE_SHA:
        raise Task17Step4AtomicCloseoutFailure("STEP4_PREMERGE_CANDIDATE_DRIFT")
    if str(receipt.get("digest") or "") != PREMERGE_DIGEST:
        raise Task17Step4AtomicCloseoutFailure("STEP4_PREMERGE_DIGEST_DRIFT")
    if str(receipt.get("failure_class") or "") != "NONE":
        raise Task17Step4AtomicCloseoutFailure("STEP4_PREMERGE_NOT_GREEN")
    return receipt


def _ensure_merged_receipt(client, *, premerge: dict, registry: dict, tree: dict, reuse: dict) -> dict:
    path = f"{RECEIPT_BASE}/{MERGED_PROOF_ID}.json"
    existing = client.content(path, ref=RECEIPT_REF, allow_404=True)
    if existing:
        receipt = _decode_json(existing, "STEP4_MERGED_RECEIPT")
        validate_runless_receipt(receipt)
        if str(receipt.get("proof_id") or "") != MERGED_PROOF_ID:
            raise Task17Step4AtomicCloseoutFailure("STEP4_MERGED_RECEIPT_ID_DRIFT")
        if str(receipt.get("candidate_sha") or "") != MAIN_SHA:
            raise Task17Step4AtomicCloseoutFailure("STEP4_MERGED_RECEIPT_SHA_DRIFT")
        if str(receipt.get("prior_digest") or "") != PREMERGE_DIGEST:
            raise Task17Step4AtomicCloseoutFailure("STEP4_MERGED_RECEIPT_PRIOR_DRIFT")
        return receipt

    artifact_map = {path: str(tree.get(path) or "") for path in premerge["artifact_map"]}
    dependency_map = {path: str(tree.get(path) or "") for path in premerge["dependency_map"]}
    receipt = build_runless_receipt(
        proof_id=MERGED_PROOF_ID,
        task_id=TASK_ID,
        project="API2",
        workstream=WORKSTREAM,
        step="task17-step4-event-driven-resume",
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
        "runless: persist Task 17 Step 4 merged-main reused receipt",
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
    registry, event_before, tree = _assert_step2a(client)
    premerge = _load_premerge_receipt(client)

    candidate_plan = _read_json(client, PLAN_PATH, SOURCE_CANDIDATE_SHA, "STEP4_CANDIDATE_POLICY")
    merged_plan = _read_json(client, PLAN_PATH, MAIN_SHA, "STEP4_MERGED_POLICY")
    candidate_tree = client.tree_blobs(SOURCE_CANDIDATE_SHA)
    candidate_artifacts = {path: str(candidate_tree.get(path) or "") for path in premerge["artifact_map"]}
    candidate_dependencies = {path: str(candidate_tree.get(path) or "") for path in premerge["dependency_map"]}
    merged_artifacts = {path: str(tree.get(path) or "") for path in premerge["artifact_map"]}
    merged_dependencies = {path: str(tree.get(path) or "") for path in premerge["dependency_map"]}
    if candidate_artifacts != dict(premerge.get("artifact_map") or {}):
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_CANDIDATE_ARTIFACT_RECEIPT_DRIFT")
    if candidate_dependencies != dict(premerge.get("dependency_map") or {}):
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_CANDIDATE_DEPENDENCY_RECEIPT_DRIFT")

    reuse = evaluate_postmerge_reuse(
        premerge_receipt=premerge,
        merged_main_sha=MAIN_SHA,
        merged_artifacts=merged_artifacts,
        merged_dependencies=merged_dependencies,
        candidate_policy=_policy(candidate_plan),
        merged_policy=_policy(merged_plan),
        candidate_is_ancestor=True,
        proof_run_id=PREMERGE_CHECK_ID,
    )
    if reuse.get("decision") != "REUSE_APPROVED" or reuse.get("reusable") is not True:
        raise Task17Step4AtomicCloseoutFailure(
            "STEP4_CLOSEOUT_REUSE_REJECTED:" + ",".join(reuse.get("reasons") or [])
        )
    if reuse.get("static_evidence_reexecuted") is not False:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_STATIC_REEXECUTION_DETECTED")
    if reuse.get("github_actions_enabled") is not False:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_ACTIONS_FALLBACK_ENABLED")

    merged_receipt = _ensure_merged_receipt(
        client,
        premerge=premerge,
        registry=registry,
        tree=tree,
        reuse=reuse,
    )
    gate_published = _ensure_gate(client, merged_receipt)

    freeze_artifacts = {path: str(tree.get(path) or "") for path in FREEZE_PATHS}
    if any(not value for value in freeze_artifacts.values()):
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_FREEZE_ARTIFACT_MISSING")
    exact_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(sorted(freeze_artifacts.items())),
    }

    entries = registry.get("entries") or {}
    existing = entries.get(FREEZE_TOKEN)
    if existing is not None:
        if existing != exact_entry:
            raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_FREEZE_TOKEN_COLLISION")
        return {
            "status": "GREEN",
            "decision": "RUNLESS_TASK17_STEP4_ALREADY_GREEN_FROZEN",
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
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_MAIN_MOVED_BEFORE_FREEZE")
    backend = GithubRegistryBackend(client)
    current_registry = backend.read_registry()
    if str(current_registry.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise Task17Step4AtomicCloseoutFailure("WAIT_REGISTRY_CAS_CONFLICT")
    try:
        client.update_content(
            REGISTRY_PATH,
            json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            backend.branch,
            "registry: freeze Runless Task 17 Step 4 event-driven resume",
            backend._blob_sha,
        )
    except Exception as exc:
        raise Task17Step4AtomicCloseoutFailure("WAIT_REGISTRY_CAS_CONFLICT") from exc

    readback = backend.read_registry()
    validate_registry(readback)
    if (readback.get("entries") or {}).get(FREEZE_TOKEN) != exact_entry:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_FREEZE_READBACK_MISMATCH")
    if readback.get("active_thaws", []) != thaws_before:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_UNRELATED_THAW_DRIFT")
    if str(readback.get("source_main_sha") or "") != MAIN_SHA:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_READBACK_MAIN_DRIFT")
    if client.branch_sha("main") != MAIN_SHA:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_MAIN_MOVED_AFTER_FREEZE")

    event_after = validate_event_resume_state(_read_json(client, EVENT_PATH, EVENT_REF, "STEP4_EVENT_STATE_READBACK"))
    if event_after != event_before:
        raise Task17Step4AtomicCloseoutFailure("STEP4_CLOSEOUT_EVENT_STATE_MUTATED")

    return {
        "status": "GREEN",
        "decision": "RUNLESS_TASK17_STEP4_GREEN_FROZEN",
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
        "event_resume_state_unchanged": True,
        "event_resume_state_hash": EXPECTED_EVENT_HASH,
        "unrelated_thaws_preserved": len(thaws_before),
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.task17_step4_atomic_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step4_atomic_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step4_atomic_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "RUNLESS_TASK17_STEP4_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.task17_step4_atomic_closeout, sort_keys=True),
            flush=True,
        )

    return app
