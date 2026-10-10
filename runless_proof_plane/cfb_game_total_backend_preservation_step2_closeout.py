from __future__ import annotations

import base64
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import (
    _hash as registry_hash,
    _payload_without_hash,
    validate_registry,
)
from devsystem.runless_terminal_proof_receipt_v1 import (
    build_runless_receipt,
    validate_runless_receipt,
)
from devsystem.scope_aware_execution_lease_v1 import (
    release_scope,
    validate_state as validate_scope_lease_state,
)

from .gate import publish_gate
from .postmerge_reuse import evaluate_postmerge_reuse
from .registry import GithubRegistryBackend, REGISTRY_PATH

TASK_ID = "cfb-game-total-backend-preservation-step2-v1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-backend-preservation-step2-v1.json"
SOURCE_MAIN_SHA = "21b6d7a0dad7edd7f6768a3f98a121572fc859fa"
SOURCE_CANDIDATE_SHA = "e44a0e3b15204033c2003302183da168f2e3d120"
MAIN_SHA = "a3166e7d980d85b6adb6a064b8ac225befd9b9e3"
PREMERGE_PROOF_ID = "cfb-game-total-backend-preservation-step2-v1-e44a0e3b15204033-c624774c620741a0"
PREMERGE_DIGEST = "0c1b15c6e54a486393a67c9690d96a02ad129a8d392c877754beec60f81dd53d"
PREMERGE_CHECK_ID = 114326836004
MERGED_PROOF_ID = "cfb-game-total-backend-preservation-step2-v1-a3166e7d980d85b6-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP2_BACKEND_PRESERVATION_V1_FROZEN"
LEASE_ID = "SCOPE-LEASE-B9CFDFEE71EBED4086F4C3CB"
LEASE_OWNER = "api2-cfb-game-total-backend-preservation-step2"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
RECEIPT_REF = "runless-proof-receipts"
RECEIPT_BASE = "devsystem/runless_proof_receipts"
RUNLESS_APP_ID = 5204253


class BackendPreservationStep2CloseoutFailure(RuntimeError):
    pass


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise BackendPreservationStep2CloseoutFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise BackendPreservationStep2CloseoutFailure(label + "_DECODE_FAILED") from exc


def _json_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


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


def _registry_summary(registry: dict) -> dict:
    return {
        "revision": int(registry["revision"]),
        "state_hash": str(registry["state_hash"]),
        "active_thaws": sorted(
            str(item.get("thaw_id") or "") for item in registry.get("active_thaws", [])
        ),
    }


def _verify_merge(client) -> dict[str, str]:
    if client.branch_sha("main") != MAIN_SHA:
        raise BackendPreservationStep2CloseoutFailure("CLOSEOUT_MAIN_DRIFT")
    commit = client.commit(MAIN_SHA)
    parents = {str(item.get("sha") or "") for item in commit.get("parents", [])}
    if SOURCE_MAIN_SHA not in parents or SOURCE_CANDIDATE_SHA not in parents:
        raise BackendPreservationStep2CloseoutFailure("CLOSEOUT_MERGE_LINEAGE_DRIFT")
    return client.tree_blobs(MAIN_SHA)


def _load_premerge_receipt(client) -> dict:
    raw = client.content(f"{RECEIPT_BASE}/{PREMERGE_PROOF_ID}.json", ref=RECEIPT_REF)
    receipt = _decode_json(raw, "PREMERGE_RECEIPT")
    validate_runless_receipt(receipt)
    if receipt.get("proof_id") != PREMERGE_PROOF_ID:
        raise BackendPreservationStep2CloseoutFailure("PREMERGE_PROOF_ID_DRIFT")
    if receipt.get("task_id") != TASK_ID or receipt.get("workstream") != WORKSTREAM:
        raise BackendPreservationStep2CloseoutFailure("PREMERGE_SCOPE_DRIFT")
    if receipt.get("candidate_sha") != SOURCE_CANDIDATE_SHA:
        raise BackendPreservationStep2CloseoutFailure("PREMERGE_CANDIDATE_DRIFT")
    if receipt.get("digest") != PREMERGE_DIGEST or receipt.get("failure_class") != "NONE":
        raise BackendPreservationStep2CloseoutFailure("PREMERGE_RECEIPT_NOT_GREEN")
    before = receipt.get("registry_before") or {}
    after = receipt.get("registry_after") or {}
    if before != after:
        raise BackendPreservationStep2CloseoutFailure("PREMERGE_REGISTRY_MUTATED")
    if int(after.get("revision") or -1) != 253:
        raise BackendPreservationStep2CloseoutFailure("PREMERGE_REGISTRY_REVISION_DRIFT")
    return receipt


def _verify_premerge_gate(client) -> None:
    runs = client.request(
        "GET",
        f"/commits/{SOURCE_CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=all&per_page=100",
    ) or {}
    exact = [run for run in runs.get("check_runs", []) if int(run.get("id") or 0) == PREMERGE_CHECK_ID]
    if len(exact) != 1:
        raise BackendPreservationStep2CloseoutFailure("PREMERGE_GATE_IDENTITY_DRIFT")
    run = exact[0]
    app_id = int(((run.get("app") or {}).get("id")) or 0)
    if (
        run.get("name") != "runless-final-gate"
        or run.get("head_sha") != SOURCE_CANDIDATE_SHA
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or app_id != RUNLESS_APP_ID
    ):
        raise BackendPreservationStep2CloseoutFailure("PREMERGE_GATE_NOT_GREEN")
    summary = str((run.get("output") or {}).get("summary") or "")
    if summary != "receipt=" + PREMERGE_DIGEST:
        raise BackendPreservationStep2CloseoutFailure("PREMERGE_GATE_RECEIPT_DRIFT")


def _ensure_merged_receipt_and_gate(
    client,
    *,
    tree: dict[str, str],
    premerge: dict,
    registry: dict,
) -> dict:
    candidate_plan = _decode_json(
        client.content(PLAN_PATH, ref=SOURCE_CANDIDATE_SHA),
        "CANDIDATE_PLAN",
    )
    merged_plan = _decode_json(client.content(PLAN_PATH, ref=MAIN_SHA), "MERGED_PLAN")
    if candidate_plan.get("probes") != [] or merged_plan.get("probes") != []:
        raise BackendPreservationStep2CloseoutFailure("CANONICAL_PROBE_POLICY_DRIFT")

    candidate_tree = client.tree_blobs(SOURCE_CANDIDATE_SHA)
    artifact_paths = list(premerge.get("artifact_map") or {})
    dependency_paths = list(premerge.get("dependency_map") or {})
    candidate_artifacts = {path: str(candidate_tree.get(path) or "") for path in artifact_paths}
    candidate_dependencies = {path: str(candidate_tree.get(path) or "") for path in dependency_paths}
    merged_artifacts = {path: str(tree.get(path) or "") for path in artifact_paths}
    merged_dependencies = {path: str(tree.get(path) or "") for path in dependency_paths}

    if candidate_artifacts != dict(premerge.get("artifact_map") or {}):
        raise BackendPreservationStep2CloseoutFailure("CANDIDATE_ARTIFACT_RECEIPT_DRIFT")
    if candidate_dependencies != dict(premerge.get("dependency_map") or {}):
        raise BackendPreservationStep2CloseoutFailure("CANDIDATE_DEPENDENCY_RECEIPT_DRIFT")
    if merged_artifacts != candidate_artifacts:
        raise BackendPreservationStep2CloseoutFailure("MERGED_ARTIFACT_DRIFT")
    if merged_dependencies != candidate_dependencies:
        raise BackendPreservationStep2CloseoutFailure("MERGED_BACKEND_DEPENDENCY_DRIFT")

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
        raise BackendPreservationStep2CloseoutFailure(
            "POSTMERGE_REUSE_REJECTED:" + ",".join(reuse.get("reasons") or [])
        )
    if reuse.get("static_evidence_reexecuted") is not False:
        raise BackendPreservationStep2CloseoutFailure("STATIC_EVIDENCE_WAS_REEXECUTED")
    if reuse.get("github_actions_enabled") is not False:
        raise BackendPreservationStep2CloseoutFailure("GITHUB_ACTIONS_FALLBACK_DRIFT")

    path = f"{RECEIPT_BASE}/{MERGED_PROOF_ID}.json"
    existing = client.content(path, ref=RECEIPT_REF, allow_404=True)
    if existing:
        merged = _decode_json(existing, "MERGED_RECEIPT")
        validate_runless_receipt(merged)
    else:
        merged = build_runless_receipt(
            proof_id=MERGED_PROOF_ID,
            task_id=TASK_ID,
            project="API2",
            workstream=WORKSTREAM,
            step="backend-preservation-step2-closeout",
            candidate_sha=MAIN_SHA,
            artifact_map=merged_artifacts,
            dependency_map=merged_dependencies,
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
            _json_text(merged),
            RECEIPT_REF,
            "runless: persist CFB Game Total backend preservation Step 2 merged receipt",
        )

    validate_runless_receipt(merged)
    if merged.get("candidate_sha") != MAIN_SHA or merged.get("prior_digest") != PREMERGE_DIGEST:
        raise BackendPreservationStep2CloseoutFailure("MERGED_RECEIPT_IDENTITY_DRIFT")
    if merged.get("static_evidence_reexecuted") is not False:
        raise BackendPreservationStep2CloseoutFailure("MERGED_RECEIPT_STATIC_RERUN_DRIFT")
    if merged.get("github_actions_enabled") is not False:
        raise BackendPreservationStep2CloseoutFailure("MERGED_RECEIPT_ACTIONS_DRIFT")

    runs = client.request(
        "GET",
        f"/commits/{MAIN_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    expected_summary = "receipt=" + str(merged["digest"])
    gate_published = True
    for run in runs.get("check_runs", []):
        output = run.get("output") or {}
        if (
            run.get("head_sha") == MAIN_SHA
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
            and int(((run.get("app") or {}).get("id")) or 0) == RUNLESS_APP_ID
            and output.get("summary") == expected_summary
        ):
            gate_published = False
            break
    if gate_published:
        publish_gate(client, MAIN_SHA, "success", merged)

    return {"receipt": merged, "reuse": reuse, "gate_published": gate_published}


def _advance_registry_and_freeze(
    client,
    *,
    tree: dict[str, str],
    premerge: dict,
) -> dict:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validated = validate_registry(registry)

    freeze_paths = sorted(
        set(premerge.get("artifact_map") or {}) | set(premerge.get("dependency_map") or {})
    )
    freeze_artifacts = {path: str(tree.get(path) or "") for path in freeze_paths}
    if any(not blob for blob in freeze_artifacts.values()):
        raise BackendPreservationStep2CloseoutFailure("FREEZE_ARTIFACT_MISSING")

    exact_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(sorted(freeze_artifacts.items())),
    }
    existing = (registry.get("entries") or {}).get(FREEZE_TOKEN)
    if str(registry.get("source_main_sha") or "") == MAIN_SHA:
        if existing != exact_entry:
            raise BackendPreservationStep2CloseoutFailure("FREEZE_READBACK_OR_TOKEN_COLLISION")
        return {
            "already_frozen": True,
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
            "artifact_count": len(freeze_artifacts),
            "unrelated_thaws_preserved": len(registry.get("active_thaws", [])),
        }

    if str(registry.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        raise BackendPreservationStep2CloseoutFailure("REGISTRY_SOURCE_MAIN_DRIFT")
    if existing is not None:
        raise BackendPreservationStep2CloseoutFailure("FREEZE_TOKEN_COLLISION")
    if client.branch_sha("main") != MAIN_SHA:
        raise BackendPreservationStep2CloseoutFailure("MAIN_MOVED_BEFORE_FREEZE")

    # Step 2 is additive-only. Before advancing the global registry baseline,
    # prove every previously frozen artifact still has its exact registered blob
    # on the merged main. This replaces any need for a fabricated thaw/update.
    frozen_baseline = dict(validated.get("artifacts") or {})
    drift = {
        path: {"expected": blob, "actual": str(tree.get(path) or "")}
        for path, blob in frozen_baseline.items()
        if str(tree.get(path) or "") != blob
    }
    if drift:
        first_path = sorted(drift)[0]
        item = drift[first_path]
        raise BackendPreservationStep2CloseoutFailure(
            "EXISTING_FROZEN_BASELINE_DRIFT:"
            + first_path
            + ":"
            + item["expected"]
            + ":"
            + item["actual"]
        )

    active_thaws_before = deepcopy(registry.get("active_thaws", []))
    updated = deepcopy(registry)
    updated["revision"] = int(registry["revision"]) + 1
    updated["source_main_sha"] = MAIN_SHA
    updated["entries"][FREEZE_TOKEN] = exact_entry
    updated["active_thaws"] = active_thaws_before
    updated.pop("state_hash", None)
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)

    if client.branch_sha("main") != MAIN_SHA:
        raise BackendPreservationStep2CloseoutFailure("MAIN_MOVED_DURING_FREEZE")
    client.update_content(
        REGISTRY_PATH,
        _json_text(updated),
        backend.branch,
        "registry: freeze CFB Game Total backend preservation Step 2",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    if str(readback.get("source_main_sha") or "") != MAIN_SHA:
        raise BackendPreservationStep2CloseoutFailure("FREEZE_READBACK_MAIN_DRIFT")
    if int(readback.get("revision") or -1) != int(registry["revision"]) + 1:
        raise BackendPreservationStep2CloseoutFailure("FREEZE_READBACK_REVISION_DRIFT")
    if (readback.get("entries") or {}).get(FREEZE_TOKEN) != exact_entry:
        raise BackendPreservationStep2CloseoutFailure("FREEZE_READBACK_MISMATCH")
    if readback.get("active_thaws", []) != active_thaws_before:
        raise BackendPreservationStep2CloseoutFailure("UNRELATED_THAW_READBACK_DRIFT")

    return {
        "already_frozen": False,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "artifact_count": len(freeze_artifacts),
        "preexisting_frozen_artifacts_verified": len(frozen_baseline),
        "unrelated_thaws_preserved": len(active_thaws_before),
    }


def _release_lease(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_lease_state(_decode_json(raw, "LEASE"))
    matches = [
        holder
        for holder in state.get("holders", [])
        if holder.get("lease_id") == LEASE_ID and holder.get("owner_id") == LEASE_OWNER
    ]
    if not matches:
        return {"released": False, "already_absent": True}
    if len(matches) != 1:
        raise BackendPreservationStep2CloseoutFailure("LEASE_IDENTITY_DRIFT")

    unrelated_before = [
        deepcopy(holder)
        for holder in state.get("holders", [])
        if holder.get("lease_id") != LEASE_ID
    ]
    released = release_scope(
        state,
        owner_id=LEASE_OWNER,
        lease_id=LEASE_ID,
        expected_revision=int(state["revision"]),
        expected_state_hash=str(state["state_hash"]),
    )
    if released["result"].get("allowed") is not True:
        raise BackendPreservationStep2CloseoutFailure(
            "LEASE_RELEASE_BLOCKED:" + str(released["result"].get("decision") or "UNKNOWN")
        )
    client.update_content(
        LEASE_PATH,
        _json_text(released["state"]),
        LEASE_BRANCH,
        "lease: release CFB Game Total backend preservation Step 2 scope",
        raw["sha"],
    )
    readback = validate_scope_lease_state(
        _decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "LEASE_READBACK")
    )
    if any(holder.get("lease_id") == LEASE_ID for holder in readback.get("holders", [])):
        raise BackendPreservationStep2CloseoutFailure("LEASE_RELEASE_READBACK_MISMATCH")
    if readback.get("holders", []) != unrelated_before:
        raise BackendPreservationStep2CloseoutFailure("UNRELATED_LEASE_READBACK_DRIFT")

    return {
        "released": True,
        "remaining_holders": len(readback.get("holders", [])),
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
    }


def execute(app):
    client = app.state.github_client
    tree = _verify_merge(client)
    premerge = _load_premerge_receipt(client)
    _verify_premerge_gate(client)
    registry = GithubRegistryBackend(client).read_registry()
    merged = _ensure_merged_receipt_and_gate(
        client,
        tree=tree,
        premerge=premerge,
        registry=registry,
    )
    frozen = _advance_registry_and_freeze(client, tree=tree, premerge=premerge)
    lease = _release_lease(client)
    if client.branch_sha("main") != MAIN_SHA:
        raise BackendPreservationStep2CloseoutFailure("MAIN_MOVED_AFTER_CLOSEOUT")

    return {
        "status": "GREEN",
        "decision": "CFB_GAME_TOTAL_BACKEND_PRESERVATION_STEP2_GREEN_FROZEN",
        "main_sha": MAIN_SHA,
        "source_candidate_sha": SOURCE_CANDIDATE_SHA,
        "premerge_check_id": PREMERGE_CHECK_ID,
        "premerge_receipt_digest": PREMERGE_DIGEST,
        "merged_receipt_digest": str(merged["receipt"]["digest"]),
        "postmerge_reuse_decision": str(merged["reuse"].get("decision") or ""),
        "freeze_token": FREEZE_TOKEN,
        "freeze": frozen,
        "lease": lease,
        "backend_product_mutations": 0,
        "static_evidence_reexecuted": False,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_backend_preservation_step2_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_backend_preservation_step2_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_backend_preservation_step2_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5200],
            }
        print(
            "CFB_GAME_TOTAL_BACKEND_PRESERVATION_STEP2_CLOSEOUT="
            + json.dumps(
                app.state.cfb_game_total_backend_preservation_step2_closeout,
                sort_keys=True,
                default=str,
            ),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
