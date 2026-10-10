from __future__ import annotations

import base64
import json
from copy import deepcopy

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
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

TASK_ID = "cfb-game-total-native-routing-step1-v1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-native-routing-step1-v1.json"
SOURCE_MAIN_SHA = "11b1dc8fcf071be46afd099268849fa9be4770af"
SOURCE_CANDIDATE_SHA = "3e28c55fa2dd55e0f9d0238a775c3e12edc1412c"
MAIN_SHA = "21b6d7a0dad7edd7f6768a3f98a121572fc859fa"
PREMERGE_PROOF_ID = "cfb-game-total-native-routing-step1-v1-3e28c55fa2dd55e0-0978694a39b7a4a3"
PREMERGE_DIGEST = "9181f9f1b022b4fe747dbd3a5c600d38874e5526dede645ec485fc374802b392"
PREMERGE_CHECK_ID = 114288746344
MERGED_PROOF_ID = "cfb-game-total-native-routing-step1-v1-21b6d7a0dad7edd7-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_ROUTING_STEP1_V1_FROZEN"
THAW_ID = "THAW-CFB-GT-NATIVE-ROUTING-STEP1-R1"
ROUTER_PATH = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
FROM_BLOB = "e5d23b77d628d17744c6249f6c87d3b6935bb9b0"
TO_BLOB = "7f27ead880acdbe6a272e6d34dfcd55d84a926d0"
LEASE_ID = "SCOPE-LEASE-CB8085920DC874CDD2A96A32"
LEASE_OWNER = "api2-cfb-game-total-native-routing-step1"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
RECEIPT_REF = "runless-proof-receipts"
RECEIPT_BASE = "devsystem/runless_proof_receipts"


class NativeRoutingStep1CloseoutFailure(RuntimeError):
    pass


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise NativeRoutingStep1CloseoutFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise NativeRoutingStep1CloseoutFailure(label + "_DECODE_FAILED") from exc


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
        raise NativeRoutingStep1CloseoutFailure("CLOSEOUT_MAIN_DRIFT")
    commit = client.commit(MAIN_SHA)
    parents = {str(item.get("sha") or "") for item in commit.get("parents", [])}
    if SOURCE_MAIN_SHA not in parents or SOURCE_CANDIDATE_SHA not in parents:
        raise NativeRoutingStep1CloseoutFailure("CLOSEOUT_MERGE_LINEAGE_DRIFT")
    tree = client.tree_blobs(MAIN_SHA)
    if str(tree.get(ROUTER_PATH) or "") != TO_BLOB:
        raise NativeRoutingStep1CloseoutFailure("CLOSEOUT_ROUTER_BLOB_DRIFT")
    return tree


def _load_premerge_receipt(client) -> dict:
    raw = client.content(f"{RECEIPT_BASE}/{PREMERGE_PROOF_ID}.json", ref=RECEIPT_REF)
    receipt = _decode_json(raw, "PREMERGE_RECEIPT")
    validate_runless_receipt(receipt)
    if receipt.get("proof_id") != PREMERGE_PROOF_ID:
        raise NativeRoutingStep1CloseoutFailure("PREMERGE_PROOF_ID_DRIFT")
    if receipt.get("candidate_sha") != SOURCE_CANDIDATE_SHA:
        raise NativeRoutingStep1CloseoutFailure("PREMERGE_CANDIDATE_DRIFT")
    if receipt.get("main_sha") != SOURCE_MAIN_SHA:
        raise NativeRoutingStep1CloseoutFailure("PREMERGE_MAIN_DRIFT")
    if receipt.get("digest") != PREMERGE_DIGEST or receipt.get("failure_class") != "NONE":
        raise NativeRoutingStep1CloseoutFailure("PREMERGE_RECEIPT_NOT_GREEN")
    if receipt.get("state") != "MERGE_AUTHORIZED" or receipt.get("status") != "MERGE_AUTHORIZED":
        raise NativeRoutingStep1CloseoutFailure("PREMERGE_AUTHORIZATION_DRIFT")
    gate = receipt.get("github_gate") or {}
    if gate.get("name") != "runless-final-gate" or gate.get("head_sha") != SOURCE_CANDIDATE_SHA:
        raise NativeRoutingStep1CloseoutFailure("PREMERGE_GATE_IDENTITY_DRIFT")
    if gate.get("conclusion") != "success" or gate.get("actions_fallback") is not False:
        raise NativeRoutingStep1CloseoutFailure("PREMERGE_GATE_NOT_GREEN")
    lease = receipt.get("lease") or {}
    if lease.get("lease_id") != LEASE_ID or lease.get("owner") != LEASE_OWNER:
        raise NativeRoutingStep1CloseoutFailure("PREMERGE_LEASE_IDENTITY_DRIFT")
    return receipt


def _ensure_merged_receipt_and_gate(client, *, tree: dict[str, str], premerge: dict, registry: dict) -> dict:
    candidate_plan = _decode_json(client.content(PLAN_PATH, ref=SOURCE_CANDIDATE_SHA), "CANDIDATE_PLAN")
    merged_plan = _decode_json(client.content(PLAN_PATH, ref=MAIN_SHA), "MERGED_PLAN")
    if candidate_plan.get("probes") != [] or merged_plan.get("probes") != []:
        raise NativeRoutingStep1CloseoutFailure("CANONICAL_PROBE_POLICY_DRIFT")

    candidate_tree = client.tree_blobs(SOURCE_CANDIDATE_SHA)
    candidate_artifacts = {path: str(candidate_tree.get(path) or "") for path in premerge["artifact_map"]}
    candidate_dependencies = {path: str(candidate_tree.get(path) or "") for path in premerge["dependency_map"]}
    merged_artifacts = {path: str(tree.get(path) or "") for path in premerge["artifact_map"]}
    merged_dependencies = {path: str(tree.get(path) or "") for path in premerge["dependency_map"]}
    if candidate_artifacts != dict(premerge.get("artifact_map") or {}):
        raise NativeRoutingStep1CloseoutFailure("CANDIDATE_ARTIFACT_RECEIPT_DRIFT")
    if candidate_dependencies != dict(premerge.get("dependency_map") or {}):
        raise NativeRoutingStep1CloseoutFailure("CANDIDATE_DEPENDENCY_RECEIPT_DRIFT")

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
        raise NativeRoutingStep1CloseoutFailure("POSTMERGE_REUSE_REJECTED:" + ",".join(reuse.get("reasons") or []))
    if reuse.get("static_evidence_reexecuted") is not False or reuse.get("github_actions_enabled") is not False:
        raise NativeRoutingStep1CloseoutFailure("POSTMERGE_REUSE_POLICY_DRIFT")

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
            step="native-routing-step1-closeout",
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
            "runless: persist CFB Game Total native routing Step 1 merged receipt",
        )
    if merged.get("candidate_sha") != MAIN_SHA or merged.get("prior_digest") != PREMERGE_DIGEST:
        raise NativeRoutingStep1CloseoutFailure("MERGED_RECEIPT_IDENTITY_DRIFT")

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
            and output.get("summary") == expected_summary
        ):
            gate_published = False
            break
    if gate_published:
        publish_gate(client, MAIN_SHA, "success", merged)
    return {"receipt": merged, "reuse": reuse, "gate_published": gate_published}


def _atomic_forward_port_and_freeze(client, *, tree: dict[str, str], premerge: dict) -> dict:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    freeze_artifacts = {path: str(tree.get(path) or "") for path in premerge["artifact_map"]}
    if any(not blob for blob in freeze_artifacts.values()):
        raise NativeRoutingStep1CloseoutFailure("FREEZE_ARTIFACT_MISSING")
    exact_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(sorted(freeze_artifacts.items())),
    }
    existing = (registry.get("entries") or {}).get(FREEZE_TOKEN)
    if str(registry.get("source_main_sha") or "") == MAIN_SHA and existing:
        if existing != exact_entry:
            raise NativeRoutingStep1CloseoutFailure("FREEZE_TOKEN_COLLISION")
        if any(g.get("thaw_id") == THAW_ID for g in registry.get("active_thaws", [])):
            raise NativeRoutingStep1CloseoutFailure("STEP1_THAW_SURVIVED_EXISTING_FREEZE")
        return {
            "already_frozen": True,
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
            "artifact_count": len(freeze_artifacts),
        }

    if str(registry.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        raise NativeRoutingStep1CloseoutFailure("REGISTRY_SOURCE_MAIN_DRIFT")
    if client.branch_sha("main") != MAIN_SHA:
        raise NativeRoutingStep1CloseoutFailure("MAIN_MOVED_BEFORE_FREEZE")
    if THAW_ID not in [str(g.get("thaw_id") or "") for g in registry.get("active_thaws", [])]:
        raise NativeRoutingStep1CloseoutFailure("EXPECTED_STEP1_THAW_MISSING")
    unrelated_before = [
        deepcopy(g) for g in registry.get("active_thaws", []) if g.get("thaw_id") != THAW_ID
    ]

    plan = plan_baseline_forward_port(
        registry,
        updates={ROUTER_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
        source_main_sha=MAIN_SHA,
    )
    updated = deepcopy(plan["registry"])
    if THAW_ID not in plan.get("retired_empty_thaw_grants", []):
        raise NativeRoutingStep1CloseoutFailure("STEP1_THAW_NOT_RETIRED")
    if updated.get("active_thaws", []) != unrelated_before:
        raise NativeRoutingStep1CloseoutFailure("UNRELATED_THAW_DRIFT")
    collision = (updated.get("entries") or {}).get(FREEZE_TOKEN)
    if collision is not None and collision != exact_entry:
        raise NativeRoutingStep1CloseoutFailure("FREEZE_TOKEN_COLLISION")
    updated["entries"][FREEZE_TOKEN] = exact_entry
    updated.pop("state_hash", None)
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)

    if client.branch_sha("main") != MAIN_SHA:
        raise NativeRoutingStep1CloseoutFailure("MAIN_MOVED_DURING_FREEZE")
    client.update_content(
        REGISTRY_PATH,
        _json_text(updated),
        backend.branch,
        "registry: freeze CFB Game Total native website routing Step 1",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    if str(readback.get("source_main_sha") or "") != MAIN_SHA:
        raise NativeRoutingStep1CloseoutFailure("FREEZE_READBACK_MAIN_DRIFT")
    if (readback.get("entries") or {}).get(FREEZE_TOKEN) != exact_entry:
        raise NativeRoutingStep1CloseoutFailure("FREEZE_READBACK_MISMATCH")
    if any(g.get("thaw_id") == THAW_ID for g in readback.get("active_thaws", [])):
        raise NativeRoutingStep1CloseoutFailure("STEP1_THAW_RETIRE_READBACK_MISMATCH")
    if readback.get("active_thaws", []) != unrelated_before:
        raise NativeRoutingStep1CloseoutFailure("UNRELATED_THAW_READBACK_DRIFT")
    return {
        "already_frozen": False,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "artifact_count": len(freeze_artifacts),
        "updated_prior_entries": len(plan.get("updated_entries") or []),
        "retired_thaw": THAW_ID,
        "unrelated_thaws_preserved": len(unrelated_before),
    }


def _release_lease(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_lease_state(_decode_json(raw, "LEASE"))
    matches = [
        h
        for h in state.get("holders", [])
        if h.get("lease_id") == LEASE_ID and h.get("owner_id") == LEASE_OWNER
    ]
    if not matches:
        return {"released": False, "already_absent": True}
    if len(matches) != 1:
        raise NativeRoutingStep1CloseoutFailure("LEASE_IDENTITY_DRIFT")
    released = release_scope(
        state,
        owner_id=LEASE_OWNER,
        lease_id=LEASE_ID,
        expected_revision=int(state["revision"]),
        expected_state_hash=str(state["state_hash"]),
    )
    if released["result"].get("allowed") is not True:
        raise NativeRoutingStep1CloseoutFailure(
            "LEASE_RELEASE_BLOCKED:" + str(released["result"].get("decision") or "UNKNOWN")
        )
    client.update_content(
        LEASE_PATH,
        _json_text(released["state"]),
        LEASE_BRANCH,
        "lease: release CFB Game Total native routing Step 1 scope",
        raw["sha"],
    )
    readback = validate_scope_lease_state(
        _decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "LEASE_READBACK")
    )
    if any(h.get("lease_id") == LEASE_ID for h in readback.get("holders", [])):
        raise NativeRoutingStep1CloseoutFailure("LEASE_RELEASE_READBACK_MISMATCH")
    return {
        "released": True,
        "remaining_holders": len(readback.get("holders", [])),
        "state_hash": str(readback["state_hash"]),
        "revision": int(readback["revision"]),
    }


def execute(app):
    client = app.state.github_client
    tree = _verify_merge(client)
    premerge = _load_premerge_receipt(client)
    registry = GithubRegistryBackend(client).read_registry()
    merged = _ensure_merged_receipt_and_gate(
        client,
        tree=tree,
        premerge=premerge,
        registry=registry,
    )
    frozen = _atomic_forward_port_and_freeze(client, tree=tree, premerge=premerge)
    lease = _release_lease(client)
    if client.branch_sha("main") != MAIN_SHA:
        raise NativeRoutingStep1CloseoutFailure("MAIN_MOVED_AFTER_CLOSEOUT")
    return {
        "status": "GREEN",
        "decision": "CFB_GAME_TOTAL_NATIVE_ROUTING_STEP1_GREEN_FROZEN",
        "main_sha": MAIN_SHA,
        "source_candidate_sha": SOURCE_CANDIDATE_SHA,
        "premerge_check_id": PREMERGE_CHECK_ID,
        "premerge_receipt_digest": PREMERGE_DIGEST,
        "merged_receipt_digest": str(merged["receipt"]["digest"]),
        "postmerge_reuse_decision": str(merged["reuse"].get("decision") or ""),
        "merged_gate_published": bool(merged["gate_published"]),
        "canonical_public_probe_required": False,
        "freeze_token": FREEZE_TOKEN,
        "freeze": frozen,
        "lease": lease,
        "static_evidence_reexecuted": False,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_native_routing_step1_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_native_routing_step1_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_native_routing_step1_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5200],
            }
        print(
            "CFB_GAME_TOTAL_NATIVE_ROUTING_STEP1_CLOSEOUT="
            + json.dumps(
                app.state.cfb_game_total_native_routing_step1_closeout,
                sort_keys=True,
                default=str,
            ),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
