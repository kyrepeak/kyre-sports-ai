"""Temporary env-gated API2 Step-4 Runless finalizer.

This file is intentionally outside frozen Runless modules. It is inert unless
STEP4_FINALIZE_ON_UVICORN=1 on the exact main Runless Render service and the
current Python process is uvicorn. It performs no GitHub Actions calls and no
product-runtime mutation.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone

FLAG = "STEP4_FINALIZE_ON_UVICORN"
SERVICE_ID = "srv-db23fee7bikc73ca8ua0"
REPOSITORY = "kyrepeak/kyre-sports-ai"
TASK_ID = "cfb-game-total-page1-v2-step4-prediction-market"
WORKSTREAM = "cfb-game-total-page1-v2"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_V2_STEP4_PREDICTION_MARKET_FROZEN"
SOURCE_CANDIDATE = "6ce49ccd5cee2a0b39af9404f6ed413e78e49f1b"
MERGED_MAIN = "091226472ad03d11d86fa2843fc37c3dc2830023"
PREMERGE_PROOF_ID = "cfb-game-total-page1-v2-step4-prediction-market-6ce49ccd5cee2a0b-acf7c2a164830ffb"
PREMERGE_DIGEST = "9829d7b5bcc735f42cccdf86ededcb09e6434435e8cf037f59533c4bcabc1710"
REUSED_PROOF_ID = f"{TASK_ID}-{MERGED_MAIN[:16]}-reused"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-prediction-market.json"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
OLD_LEASE_OWNER = "api2-cfb-game-total-page1-v2-step4"
OLD_LEASE_ID = "SCOPE-LEASE-2FEF82C73C72C46AE97410C9"
CLOSEOUT_OWNER = "api2-finalization-cfb-game-total-page1-v2-step4"
RECEIPT_BRANCH = "runless-proof-receipts"
RECEIPT_BASE = "devsystem/runless_proof_receipts"
REUSED_RECEIPT_PATH = f"{RECEIPT_BASE}/{REUSED_PROOF_ID}.json"
EXPECTED_REGISTRY_REVISION = 196
EXPECTED_REGISTRY_HASH = "b6779f297868cae2388f18bc60bc43ae42ee181742bb5f55ff87f43d1668d8c1"
EXPECTED_BASE_MAIN = "8ad570f765daf0884fe6f963f10982b05a414b60"

ARTIFACTS = {
    "cfb_game_total_clean_page_v37.py": "6071b8437f25560996e4922705efc3400ad5ebdd",
    "cfb_game_total_page1_step4_prediction_market_v1.py": "6665b304009fb047482151abe34713250c597a92",
    "cfb_game_total_page1_step4_side_market_v1.py": "249f123885e7a64c2ab7ef8d3fe50a8c03c3129f",
    "cfb_game_total_page1_v2_step4_activation.py": "9fc633200a38a7f0c560696f9a57cb2c0ed09c0f",
    "devsystem/execution_plans/cfb-game-total-page1-v2-step4-prediction-market.json": "35999cee728a22394c869622651e884effbb58b5",
    "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-prediction-market.json": "a454afcbb0e77084c4d9628d3ba74dc8201a98b3",
    "devsystem/task_ledgers/cfb-game-total-page1-v2-step4-prediction-market.json": "62caa31ab79084df184896813dde4726bda04325",
    "kyre_universal_components_v1.py": "cd9062290c3916e453451f0d3cfd83b93b3510a3",
    "tests/test_cfb_game_total_page1_v2_step4_prediction_market.py": "78c0888dc0744f07a179d4cf6d5aefc18b9035a2",
}
DEPENDENCIES = {
    "cfb_game_total_clean_page_v11.py": "5cd70939d93717d5b5d85cb66812605c0cceadb8",
    "cfb_game_total_clean_page_v26.py": "d9cbc1ca2703f0b10e655dee22ec658085153dbf",
    "cfb_game_total_clean_page_v35.py": "52c67f5e14502abda616b900a6c961441725d584",
    "cfb_game_total_clean_page_v36.py": "3970337b170ccdc44870699a8a35cf800dea6867",
    "cfb_game_total_page1_step3_presentation_v1.py": "13c0deabcacba311999447608eafd07eef778565",
    "cfb_game_total_page1_v2_step3_activation.py": "2d5b79be2d93455e0cf612b4ca1901fe412cc0c9",
    "cfb_top_picks_market_context_v1.py": "2f6e849772764a5efbf69926d3e942967df7b82a",
    "kyre_universal_shell_runtime_v1.py": "40a37ff350262256f590a430ea9494d52c0c5304",
    "streamlit_memory_lazy_router_v190.py": "fca1442c144d8ff02868ed0371a92f72257d697e",
}


def _enabled() -> bool:
    argv0 = os.path.basename(sys.argv[0] or "").lower()
    return (
        os.environ.get(FLAG, "").strip() == "1"
        and os.environ.get("RENDER_SERVICE_ID", "").strip() == SERVICE_ID
        and "uvicorn" in argv0
    )


def _decode_json(raw: dict) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("STEP4_FINALIZE_CONTENT_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode("utf-8"))


def _encode_state(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _policy(plan: dict) -> dict:
    return {
        "commands": plan.get("commands") or [],
        "probes": plan.get("probes") or [],
        "timeout_seconds": int(plan.get("timeout_seconds", 0)),
        "live_ttl_seconds": int(plan.get("live_ttl_seconds", 0)),
        "freeze_token": str(plan.get("freeze_token") or ""),
    }


def _run() -> None:
    from devsystem.frozen_artifact_registry_v1 import validate_registry
    from devsystem.runless_terminal_proof_receipt_v1 import (
        build_runless_receipt,
        validate_runless_receipt,
    )
    from devsystem.scope_aware_execution_lease_v1 import (
        build_scope,
        claim_scope,
        release_scope,
        validate_state as validate_lease_state,
    )
    from runless_proof_plane.config import Settings
    from runless_proof_plane.gate import publish_gate
    from runless_proof_plane.github_app import GithubAppAuth
    from runless_proof_plane.github_client import GithubClient
    from runless_proof_plane.postmerge_reuse import evaluate_postmerge_reuse
    from runless_proof_plane.receipts import GithubReceiptBackend, ReceiptStore
    from runless_proof_plane.registry import _state_hash

    settings = Settings.from_env()
    if settings.bootstrap:
        raise RuntimeError("STEP4_FINALIZE_RUNLESS_FULL_MODE_REQUIRED")
    if settings.repository != REPOSITORY:
        raise RuntimeError("STEP4_FINALIZE_REPOSITORY_DRIFT")
    client = GithubClient(GithubAppAuth(settings), REPOSITORY)

    # Step 2A exact identity: repository/main/merge ancestry.
    if client.branch_sha("main") != MERGED_MAIN:
        raise RuntimeError("STEP4_FINALIZE_MAIN_DRIFT")
    merged_commit = client.commit(MERGED_MAIN)
    parent_shas = {str(p.get("sha") or "") for p in merged_commit.get("parents", [])}
    if SOURCE_CANDIDATE not in parent_shas:
        raise RuntimeError("STEP4_FINALIZE_MERGE_ANCESTRY_DRIFT")

    merged_tree = client.tree_blobs(MERGED_MAIN)
    candidate_tree = client.tree_blobs(SOURCE_CANDIDATE)
    for path, blob in {**ARTIFACTS, **DEPENDENCIES}.items():
        if candidate_tree.get(path) != blob or merged_tree.get(path) != blob:
            raise RuntimeError("STEP4_FINALIZE_CONTENT_IDENTITY_DRIFT:" + path)

    pre_raw = client.content(f"{RECEIPT_BASE}/{PREMERGE_PROOF_ID}.json", ref=RECEIPT_BRANCH)
    pre = _decode_json(pre_raw)
    validate_runless_receipt(pre)
    if (
        pre.get("digest") != PREMERGE_DIGEST
        or pre.get("candidate_sha") != SOURCE_CANDIDATE
        or pre.get("task_id") != TASK_ID
        or pre.get("workstream") != WORKSTREAM
        or pre.get("failure_class") != "NONE"
        or dict(pre.get("artifact_map") or {}) != ARTIFACTS
        or dict(pre.get("dependency_map") or {}) != DEPENDENCIES
    ):
        raise RuntimeError("STEP4_FINALIZE_PREMERGE_RECEIPT_DRIFT")

    candidate_plan = _decode_json(client.content(PLAN_PATH, ref=SOURCE_CANDIDATE))
    merged_plan = _decode_json(client.content(PLAN_PATH, ref=MERGED_MAIN))
    if candidate_plan != merged_plan:
        raise RuntimeError("STEP4_FINALIZE_PLAN_DRIFT")
    if merged_plan.get("probes"):
        raise RuntimeError("STEP4_FINALIZE_DYNAMIC_PROOF_REUSE_BLOCKED")
    if merged_plan.get("freeze_token") != FREEZE_TOKEN:
        raise RuntimeError("STEP4_FINALIZE_FREEZE_TOKEN_DRIFT")

    reuse = evaluate_postmerge_reuse(
        premerge_receipt=pre,
        merged_main_sha=MERGED_MAIN,
        merged_artifacts={p: merged_tree[p] for p in ARTIFACTS},
        merged_dependencies={p: merged_tree[p] for p in DEPENDENCIES},
        candidate_policy=_policy(candidate_plan),
        merged_policy=_policy(merged_plan),
        candidate_is_ancestor=True,
        proof_run_id=max(1, int(SOURCE_CANDIDATE[:8], 16)),
    )
    if reuse.get("decision") != "REUSE_APPROVED" or reuse.get("reusable") is not True:
        raise RuntimeError("STEP4_FINALIZE_REUSE_REJECTED:" + json.dumps(reuse, sort_keys=True))

    # Canonical registry snapshot and Step-3 prerequisite.
    registry_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    registry_blob = registry_raw["sha"]
    registry = _decode_json(registry_raw)
    validate_registry(registry)
    existing = (registry.get("entries") or {}).get(FREEZE_TOKEN)
    exact_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MERGED_MAIN,
        "artifacts": dict(ARTIFACTS),
    }
    if existing is not None and dict(existing) != exact_entry:
        raise RuntimeError("STEP4_FINALIZE_EXISTING_FREEZE_DRIFT")
    if "CFB_GAME_TOTAL_PAGE1_V2_STEP3_MATCHUP_HERO_PHX_FROZEN" not in registry.get("entries", {}):
        raise RuntimeError("STEP4_FINALIZE_STEP3_FREEZE_MISSING")
    if existing is None and (
        int(registry.get("revision", -1)) != EXPECTED_REGISTRY_REVISION
        or registry.get("state_hash") != EXPECTED_REGISTRY_HASH
        or registry.get("source_main_sha") != EXPECTED_BASE_MAIN
    ):
        raise RuntimeError("STEP4_FINALIZE_REGISTRY_DRIFT")

    # Step 2A authority handoff: retire the exact premerge holder and acquire
    # a closeout-only lease for registry + receipt mutation, in one CAS write.
    lease_raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    lease_blob = lease_raw["sha"]
    lease_state = validate_lease_state(_decode_json(lease_raw))
    target_holders = [
        h for h in lease_state.get("holders", [])
        if h.get("owner_id") == OLD_LEASE_OWNER and h.get("lease_id") == OLD_LEASE_ID
    ]
    closeout_holders = [h for h in lease_state.get("holders", []) if h.get("owner_id") == CLOSEOUT_OWNER]
    closeout_lease_id = None
    if closeout_holders:
        if len(closeout_holders) != 1:
            raise RuntimeError("STEP4_FINALIZE_CLOSEOUT_LEASE_AMBIGUOUS")
        closeout_lease_id = str(closeout_holders[0]["lease_id"])
    elif existing is None:
        if len(target_holders) != 1:
            raise RuntimeError("STEP4_FINALIZE_PREMERGE_LEASE_DRIFT")
        ident = dict((target_holders[0].get("scope") or {}).get("resource_identity") or {})
        if ident.get("candidate") != SOURCE_CANDIDATE or ident.get("pr") != "1464":
            raise RuntimeError("STEP4_FINALIZE_PREMERGE_LEASE_IDENTITY_DRIFT")
        released = release_scope(
            lease_state,
            owner_id=OLD_LEASE_OWNER,
            lease_id=OLD_LEASE_ID,
            expected_revision=lease_state["revision"],
            expected_state_hash=lease_state["state_hash"],
        )
        if released["result"].get("decision") != "SCOPE_LEASE_RELEASED":
            raise RuntimeError("STEP4_FINALIZE_PREMERGE_LEASE_RELEASE_FAILED")
        handoff = released["state"]
        scope = build_scope(
            write_paths=[REGISTRY_PATH, REUSED_RECEIPT_PATH],
            shared_resources=[WORKSTREAM],
            resource_identity={
                "candidate": SOURCE_CANDIDATE,
                "main_sha": MERGED_MAIN,
                "registry_state_hash": registry["state_hash"],
                "freeze_token": FREEZE_TOKEN,
            },
        )
        claimed = claim_scope(
            handoff,
            owner_id=CLOSEOUT_OWNER,
            now_utc=_utc_now(),
            scope=scope,
            expected_revision=handoff["revision"],
            expected_state_hash=handoff["state_hash"],
            ttl_seconds=900,
            frozen_paths=(),
            thawed_paths=(),
        )
        if claimed["result"].get("decision") != "SCOPE_LEASE_ACQUIRED":
            raise RuntimeError("STEP4_FINALIZE_CLOSEOUT_LEASE_CLAIM_FAILED")
        lease_next = claimed["state"]
        closeout_lease_id = str(claimed["result"]["lease_id"])
        client.update_content(
            LEASE_PATH,
            _encode_state(lease_next),
            LEASE_BRANCH,
            "lease: handoff CFB Game Total Step 4 to finalization authority",
            lease_blob,
        )
        lease_rb = validate_lease_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH)))
        if not any(h.get("owner_id") == CLOSEOUT_OWNER and h.get("lease_id") == closeout_lease_id for h in lease_rb.get("holders", [])):
            raise RuntimeError("STEP4_FINALIZE_CLOSEOUT_LEASE_READBACK_FAILED")

    # Re-read registry after authority acquisition. No shared-state drift allowed.
    registry_raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    registry_blob = registry_raw["sha"]
    registry = _decode_json(registry_raw)
    validate_registry(registry)
    existing = (registry.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is None and (
        int(registry.get("revision", -1)) != EXPECTED_REGISTRY_REVISION
        or registry.get("state_hash") != EXPECTED_REGISTRY_HASH
    ):
        raise RuntimeError("STEP4_FINALIZE_REGISTRY_CHANGED_AFTER_AUTHORITY")

    registry_receipt = {
        "revision": int(registry["revision"]),
        "state_hash": str(registry["state_hash"]),
        "active_thaws": [str(x.get("thaw_id")) for x in registry.get("active_thaws", [])],
    }
    receipt_backend = GithubReceiptBackend(client, MERGED_MAIN, RECEIPT_BRANCH, RECEIPT_BASE)
    receipt_store = ReceiptStore(receipt_backend, RECEIPT_BRANCH, RECEIPT_BASE)
    receipt_path = f"{RECEIPT_BASE}/{REUSED_PROOF_ID}.json"
    if receipt_backend.exists(receipt_path, RECEIPT_BRANCH):
        merged_receipt = receipt_store.get(REUSED_PROOF_ID)
        if (
            merged_receipt.get("candidate_sha") != MERGED_MAIN
            or merged_receipt.get("prior_digest") != PREMERGE_DIGEST
            or merged_receipt.get("artifact_map") != ARTIFACTS
        ):
            raise RuntimeError("STEP4_FINALIZE_REUSED_RECEIPT_DRIFT")
    else:
        merged_receipt = build_runless_receipt(
            proof_id=REUSED_PROOF_ID,
            task_id=TASK_ID,
            project="API2",
            workstream=WORKSTREAM,
            step=TASK_ID,
            candidate_sha=MERGED_MAIN,
            artifact_map=ARTIFACTS,
            dependency_map=DEPENDENCIES,
            registry_before=registry_receipt,
            registry_after=registry_receipt,
            evidence_digests=list(pre.get("evidence_digests") or []),
            failure_class="NONE",
            prior_digest=PREMERGE_DIGEST,
            proof_fingerprint=pre.get("proof_fingerprint"),
            reuse_content_fingerprint=reuse.get("content_fingerprint"),
            reused_from_proof_id=PREMERGE_PROOF_ID,
            reused_from_receipt_digest=PREMERGE_DIGEST,
            static_evidence_reexecuted=False,
            github_actions_enabled=False,
        )
        receipt_store.put(merged_receipt)

    # Idempotent reused gate: publish only if exact receipt gate is absent.
    checks = client.request("GET", f"/commits/{MERGED_MAIN}/check-runs") or {}
    gate_seen = False
    for check in checks.get("check_runs", []):
        if check.get("name") == settings.gate_name and check.get("conclusion") == "success":
            summary = str(((check.get("output") or {}).get("summary") or ""))
            if merged_receipt["digest"] in summary:
                gate_seen = True
                break
    if not gate_seen:
        publish_gate(client, MERGED_MAIN, "success", merged_receipt, settings.gate_name)

    # Exact-artifact CAS freeze preserving unrelated active thaws byte-for-byte.
    if existing is None:
        thaw_paths = {
            path
            for grant in registry.get("active_thaws", [])
            for path in (grant.get("files") or {})
        }
        overlap = sorted(set(ARTIFACTS) & thaw_paths)
        if overlap:
            raise RuntimeError("STEP4_FINALIZE_CONFLICTING_THAW:" + ",".join(overlap))
        flattened = {}
        for entry in registry.get("entries", {}).values():
            flattened.update(entry.get("artifacts") or {})
        conflicts = sorted(p for p, blob in ARTIFACTS.items() if p in flattened and flattened[p] != blob)
        if conflicts:
            raise RuntimeError("STEP4_FINALIZE_FROZEN_BASELINE_CONFLICT:" + ",".join(conflicts))
        updated = deepcopy(registry)
        updated["revision"] = int(registry["revision"]) + 1
        updated["source_main_sha"] = MERGED_MAIN
        updated["entries"][FREEZE_TOKEN] = exact_entry
        updated["active_thaws"] = deepcopy(registry.get("active_thaws", []))
        updated["state_hash"] = _state_hash(updated)
        validate_registry(updated)
        client.update_content(
            REGISTRY_PATH,
            _encode_state(updated),
            REGISTRY_BRANCH,
            "registry: freeze CFB Game Total Page 1 V2 Step 4",
            registry_blob,
        )

    # Canonical read-back is mandatory before GREEN+FROZEN.
    final_registry = _decode_json(client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH))
    validate_registry(final_registry)
    final_entry = (final_registry.get("entries") or {}).get(FREEZE_TOKEN)
    if dict(final_entry or {}) != exact_entry:
        raise RuntimeError("STEP4_FINALIZE_REGISTRY_READBACK_MISMATCH")
    if final_registry.get("source_main_sha") != MERGED_MAIN:
        raise RuntimeError("STEP4_FINALIZE_REGISTRY_MAIN_READBACK_MISMATCH")

    # Authority GC: release only the exact closeout holder and prove zero
    # remaining authority for this workstream.
    lease_raw2 = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    lease_blob2 = lease_raw2["sha"]
    lease2 = validate_lease_state(_decode_json(lease_raw2))
    holders = [h for h in lease2.get("holders", []) if h.get("owner_id") == CLOSEOUT_OWNER]
    if holders:
        if len(holders) != 1 or (closeout_lease_id and holders[0].get("lease_id") != closeout_lease_id):
            raise RuntimeError("STEP4_FINALIZE_AUTHORITY_GC_IDENTITY_DRIFT")
        released2 = release_scope(
            lease2,
            owner_id=CLOSEOUT_OWNER,
            lease_id=str(holders[0]["lease_id"]),
            expected_revision=lease2["revision"],
            expected_state_hash=lease2["state_hash"],
        )
        if released2["result"].get("decision") != "SCOPE_LEASE_RELEASED":
            raise RuntimeError("STEP4_FINALIZE_AUTHORITY_GC_FAILED")
        client.update_content(
            LEASE_PATH,
            _encode_state(released2["state"]),
            LEASE_BRANCH,
            "lease: release CFB Game Total Step 4 finalization authority",
            lease_blob2,
        )
    lease_final = validate_lease_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH)))
    target_holders = [
        h for h in lease_final.get("holders", [])
        if WORKSTREAM in ((h.get("scope") or {}).get("shared_resources") or [])
        or h.get("owner_id") in {OLD_LEASE_OWNER, CLOSEOUT_OWNER}
    ]
    if target_holders:
        raise RuntimeError("STEP4_FINALIZE_TARGET_AUTHORITY_REMAINS")

    print(
        "STEP4_FINALIZATION_GREEN_FROZEN="
        + json.dumps(
            {
                "freeze_token": FREEZE_TOKEN,
                "main_sha": MERGED_MAIN,
                "registry_revision": final_registry["revision"],
                "registry_state_hash": final_registry["state_hash"],
                "reused_receipt_digest": merged_receipt["digest"],
                "premerge_receipt_digest": PREMERGE_DIGEST,
                "artifact_count": len(ARTIFACTS),
                "dependency_count": len(DEPENDENCIES),
                "active_thaw_count": len(final_registry.get("active_thaws", [])),
                "target_authority_count": 0,
                "github_actions_fallback": 0,
                "sportsbook_projection_influence": 0.0,
            },
            sort_keys=True,
        ),
        flush=True,
    )


if _enabled():
    try:
        _run()
    except BaseException as exc:
        print(
            "STEP4_FINALIZATION_FAILED=" + type(exc).__name__ + ":" + str(exc)[:500],
            flush=True,
        )
        os._exit(93)
