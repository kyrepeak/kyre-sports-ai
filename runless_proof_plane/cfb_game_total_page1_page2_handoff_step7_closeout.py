from __future__ import annotations

import base64
import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import _hash as registry_hash, _payload_without_hash, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt, validate_runless_receipt
from devsystem.scope_aware_execution_lease_v1 import release_scope, validate_state as validate_scope_lease_state

from .gate import publish_gate
from .postmerge_reuse import evaluate_postmerge_reuse
from .registry import GithubRegistryBackend, REGISTRY_PATH

TASK_ID = "cfb-game-total-page1-page2-handoff-step7-v1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-page1-page2-handoff-step7-v1.json"
SOURCE_MAIN_SHA = "0baa35045941adfea5d7a5bafb216efbfed42b7a"
SOURCE_CANDIDATE_SHA = "be6a0ddbee8cb85fb9e014a7d6fc1557c25a1a3e"
MAIN_SHA = "36e0d3ee8de1a72bdeeb5e007334df1e8c5a3adb"
PREMERGE_PROOF_ID = "cfb-game-total-page1-page2-handoff-step7-v1-be6a0ddbee8cb85f-ae4fc8f1865de7c7"
PREMERGE_DIGEST = "1f4fe43f0d7d78f94b5f29099f779c2209b2e9d78807dd872aedb20c7599b578"
PREMERGE_CHECK_ID = 114355985598
MERGED_PROOF_ID = "cfb-game-total-page1-page2-handoff-step7-v1-36e0d3ee8de1a72b-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP7_PAGE1_PAGE2_HANDOFF_V1_FROZEN"
LEASE_ID = "SCOPE-LEASE-D24C5C7B4F365450B02639CB"
LEASE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step7"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
RECEIPT_REF = "runless-proof-receipts"
RECEIPT_BASE = "devsystem/runless_proof_receipts"


class Step7CloseoutFailure(RuntimeError):
    pass


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise Step7CloseoutFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise Step7CloseoutFailure(label + "_DECODE_FAILED") from exc


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
        "active_thaws": sorted(str(item.get("thaw_id") or "") for item in registry.get("active_thaws", [])),
    }


def _verify_merge(client) -> dict[str, str]:
    if client.branch_sha("main") != MAIN_SHA:
        raise Step7CloseoutFailure("CLOSEOUT_MAIN_DRIFT")
    commit = client.commit(MAIN_SHA)
    parents = {str(item.get("sha") or "") for item in commit.get("parents", [])}
    if SOURCE_MAIN_SHA not in parents or SOURCE_CANDIDATE_SHA not in parents:
        raise Step7CloseoutFailure("CLOSEOUT_MERGE_LINEAGE_DRIFT")
    return client.tree_blobs(MAIN_SHA)


def _load_premerge_receipt(client) -> dict:
    raw = client.content(f"{RECEIPT_BASE}/{PREMERGE_PROOF_ID}.json", ref=RECEIPT_REF)
    receipt = _decode_json(raw, "PREMERGE_RECEIPT")
    validate_runless_receipt(receipt)
    if receipt.get("proof_id") != PREMERGE_PROOF_ID:
        raise Step7CloseoutFailure("PREMERGE_PROOF_ID_DRIFT")
    if receipt.get("task_id") != TASK_ID or receipt.get("workstream") != WORKSTREAM:
        raise Step7CloseoutFailure("PREMERGE_SCOPE_DRIFT")
    if receipt.get("candidate_sha") != SOURCE_CANDIDATE_SHA:
        raise Step7CloseoutFailure("PREMERGE_CANDIDATE_DRIFT")
    if receipt.get("digest") != PREMERGE_DIGEST or receipt.get("failure_class") != "NONE":
        raise Step7CloseoutFailure("PREMERGE_RECEIPT_NOT_GREEN")
    if receipt.get("registry_before") != receipt.get("registry_after"):
        raise Step7CloseoutFailure("PREMERGE_REGISTRY_MUTATED")
    return receipt


def _verify_premerge_gate(client) -> None:
    runs = client.request(
        "GET",
        f"/commits/{SOURCE_CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    found = any(
        int(run.get("id") or 0) == PREMERGE_CHECK_ID
        and run.get("head_sha") == SOURCE_CANDIDATE_SHA
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        for run in runs.get("check_runs", [])
    )
    if not found:
        raise Step7CloseoutFailure("PREMERGE_GATE_NOT_GREEN")


def _ensure_merged_receipt_and_gate(client, *, tree: dict[str, str], premerge: dict, registry: dict) -> dict:
    candidate_plan = _decode_json(client.content(PLAN_PATH, ref=SOURCE_CANDIDATE_SHA), "CANDIDATE_PLAN")
    merged_plan = _decode_json(client.content(PLAN_PATH, ref=MAIN_SHA), "MERGED_PLAN")
    if candidate_plan.get("probes") != [] or merged_plan.get("probes") != []:
        raise Step7CloseoutFailure("CANONICAL_PROBE_POLICY_DRIFT")

    candidate_tree = client.tree_blobs(SOURCE_CANDIDATE_SHA)
    candidate_artifacts = {path: str(candidate_tree.get(path) or "") for path in premerge["artifact_map"]}
    candidate_dependencies = {path: str(candidate_tree.get(path) or "") for path in premerge["dependency_map"]}
    merged_artifacts = {path: str(tree.get(path) or "") for path in premerge["artifact_map"]}
    merged_dependencies = {path: str(tree.get(path) or "") for path in premerge["dependency_map"]}
    if candidate_artifacts != dict(premerge.get("artifact_map") or {}):
        raise Step7CloseoutFailure("CANDIDATE_ARTIFACT_RECEIPT_DRIFT")
    if candidate_dependencies != dict(premerge.get("dependency_map") or {}):
        raise Step7CloseoutFailure("CANDIDATE_DEPENDENCY_RECEIPT_DRIFT")

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
        raise Step7CloseoutFailure("POSTMERGE_REUSE_REJECTED:" + ",".join(reuse.get("reasons") or []))
    if reuse.get("static_evidence_reexecuted") is not False or reuse.get("github_actions_enabled") is not False:
        raise Step7CloseoutFailure("POSTMERGE_REUSE_POLICY_DRIFT")

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
            step="page1-page2-handoff-step7-closeout",
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
        client.put_content(path, _json_text(merged), RECEIPT_REF, "runless: persist CFB Game Total Step 7 merged receipt")
    if merged.get("candidate_sha") != MAIN_SHA or merged.get("prior_digest") != PREMERGE_DIGEST:
        raise Step7CloseoutFailure("MERGED_RECEIPT_IDENTITY_DRIFT")

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


def _atomic_additive_freeze(client, *, tree: dict[str, str], premerge: dict) -> dict:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    freeze_artifacts = {path: str(tree.get(path) or "") for path in premerge["artifact_map"]}
    if any(not blob for blob in freeze_artifacts.values()):
        raise Step7CloseoutFailure("FREEZE_ARTIFACT_MISSING")
    exact_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(sorted(freeze_artifacts.items())),
    }
    existing = (registry.get("entries") or {}).get(FREEZE_TOKEN)
    if str(registry.get("source_main_sha") or "") == MAIN_SHA and existing:
        if existing != exact_entry:
            raise Step7CloseoutFailure("FREEZE_TOKEN_COLLISION")
        return {
            "already_frozen": True,
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
            "artifact_count": len(freeze_artifacts),
            "unrelated_thaws_preserved": len(registry.get("active_thaws", [])),
        }

    if str(registry.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        raise Step7CloseoutFailure("REGISTRY_SOURCE_MAIN_DRIFT")
    if client.branch_sha("main") != MAIN_SHA:
        raise Step7CloseoutFailure("MAIN_MOVED_BEFORE_FREEZE")

    unrelated_before = deepcopy(registry.get("active_thaws", []))
    flattened: dict[str, str] = {}
    for entry in (registry.get("entries") or {}).values():
        for path, blob in (entry.get("artifacts") or {}).items():
            prior = flattened.get(str(path))
            if prior is not None and prior != str(blob):
                raise Step7CloseoutFailure("PREEXISTING_FROZEN_BASELINE_CONFLICT:" + str(path))
            flattened[str(path)] = str(blob)
    conflicts = sorted(path for path, blob in freeze_artifacts.items() if path in flattened and flattened[path] != blob)
    if conflicts:
        raise Step7CloseoutFailure("STEP7_FROZEN_PATH_CONFLICT:" + ",".join(conflicts))
    thaw_paths = {str(path) for grant in unrelated_before for path in (grant.get("files") or {})}
    overlap = sorted(set(freeze_artifacts) & thaw_paths)
    if overlap:
        raise Step7CloseoutFailure("STEP7_ACTIVE_THAW_OVERLAP:" + ",".join(overlap))

    updated = deepcopy(registry)
    updated["revision"] = int(registry["revision"]) + 1
    updated["source_main_sha"] = MAIN_SHA
    updated["entries"][FREEZE_TOKEN] = exact_entry
    updated["active_thaws"] = unrelated_before
    updated.pop("state_hash", None)
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)

    if client.branch_sha("main") != MAIN_SHA:
        raise Step7CloseoutFailure("MAIN_MOVED_DURING_FREEZE")
    client.update_content(
        REGISTRY_PATH,
        _json_text(updated),
        backend.branch,
        "registry: freeze CFB Game Total Page 1 to Page 2 handoff Step 7",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    if str(readback.get("source_main_sha") or "") != MAIN_SHA:
        raise Step7CloseoutFailure("FREEZE_READBACK_MAIN_DRIFT")
    if (readback.get("entries") or {}).get(FREEZE_TOKEN) != exact_entry:
        raise Step7CloseoutFailure("FREEZE_READBACK_MISMATCH")
    if readback.get("active_thaws", []) != unrelated_before:
        raise Step7CloseoutFailure("UNRELATED_THAW_READBACK_DRIFT")
    return {
        "already_frozen": False,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "artifact_count": len(freeze_artifacts),
        "unrelated_thaws_preserved": len(unrelated_before),
        "additive_only": True,
        "retired_thaw": None,
    }


def _release_lease(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_lease_state(_decode_json(raw, "LEASE"))
    matches = [h for h in state.get("holders", []) if h.get("lease_id") == LEASE_ID and h.get("owner_id") == LEASE_OWNER]
    if not matches:
        return {"released": False, "already_absent": True, "remaining_holders": len(state.get("holders", []))}
    if len(matches) != 1:
        raise Step7CloseoutFailure("LEASE_IDENTITY_DRIFT")
    released = release_scope(
        state,
        owner_id=LEASE_OWNER,
        lease_id=LEASE_ID,
        expected_revision=int(state["revision"]),
        expected_state_hash=str(state["state_hash"]),
    )
    if released["result"].get("allowed") is not True:
        raise Step7CloseoutFailure("LEASE_RELEASE_BLOCKED:" + str(released["result"].get("decision") or "UNKNOWN"))
    client.update_content(
        LEASE_PATH,
        _json_text(released["state"]),
        LEASE_BRANCH,
        "lease: release CFB Game Total Step 7 scope",
        raw["sha"],
    )
    readback = validate_scope_lease_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "LEASE_READBACK"))
    if any(h.get("lease_id") == LEASE_ID for h in readback.get("holders", [])):
        raise Step7CloseoutFailure("LEASE_RELEASE_READBACK_MISMATCH")
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
    _verify_premerge_gate(client)
    registry = GithubRegistryBackend(client).read_registry()
    merged = _ensure_merged_receipt_and_gate(client, tree=tree, premerge=premerge, registry=registry)
    frozen = _atomic_additive_freeze(client, tree=tree, premerge=premerge)
    lease = _release_lease(client)
    if client.branch_sha("main") != MAIN_SHA:
        raise Step7CloseoutFailure("MAIN_MOVED_AFTER_CLOSEOUT")
    return {
        "status": "GREEN",
        "decision": "CFB_GAME_TOTAL_PAGE1_PAGE2_HANDOFF_STEP7_GREEN_FROZEN",
        "step": "7/8",
        "main_sha": MAIN_SHA,
        "source_candidate_sha": SOURCE_CANDIDATE_SHA,
        "premerge_check_id": PREMERGE_CHECK_ID,
        "premerge_receipt_digest": PREMERGE_DIGEST,
        "merged_receipt_digest": str(merged["receipt"]["digest"]),
        "postmerge_reuse_decision": str(merged["reuse"].get("decision") or ""),
        "freeze_token": FREEZE_TOKEN,
        "freeze": frozen,
        "lease": lease,
        "page1_owner": "cfb_game_total_clean_page_v43",
        "selected_day_data_owner": "cfb_game_total_clean_page_v42",
        "page2_runtime": "cfb_game_total_page2_step8_final_runtime_v1",
        "phoenix_timezone": "America/Phoenix",
        "product_files_modified": 0,
        "static_evidence_reexecuted": False,
        "github_actions_fallback": 0,
        "step8_started": False,
    }


def install_startup(app):
    app.state.cfb_game_total_page1_page2_handoff_step7_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page1_page2_handoff_step7_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page1_page2_handoff_step7_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5200],
            }
        print(
            "CFB_GAME_TOTAL_PAGE1_PAGE2_HANDOFF_STEP7_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_page1_page2_handoff_step7_closeout, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
