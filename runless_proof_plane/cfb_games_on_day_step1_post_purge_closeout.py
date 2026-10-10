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

WORKSTREAM = "cfb-game-total-games-on-day-v1"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-games-on-day-step1-card-layout-v1.json"
SOURCE_MAIN_SHA = "f15fe559fdaab801deb77c43c6451bc811159fed"
SOURCE_CANDIDATE_SHA = "58f237846007e2a0d036471d238b6c6fd9edcdc7"
MAIN_SHA = "403e3cb9d7b0e11c4bfc15de512fb1a862e88549"
PREMERGE_PROOF_ID = "cfb-game-total-games-on-day-step1-card-layout-v1-58f237846007e2a0-57bda737afbd3b62"
PREMERGE_DIGEST = "a4f5c82928425253502efd5880f8aeac5aa28f680e0c3987364a9cbf17fdaca3"
PREMERGE_CHECK_ID = 114155217596
MERGED_PROOF_ID = "cfb-game-total-games-on-day-step1-card-layout-v1-403e3cb9d7b0e11c-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_GAMES_ON_DAY_STEP1_CARD_LAYOUT_V1_FROZEN"
EXPECTED_REGISTRY_REVISION = 242
EXPECTED_REGISTRY_HASH = "f218d7954d81b2d476c2acda2b9b53d18c72d1d88290d62c2499ab8220f4e56e"
LEASE_ID = "SCOPE-LEASE-1E6EB6A9E37AEFB89F845E21"
LEASE_OWNER = "api2-cfb-games-on-day-step1-post-purge"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
RECEIPT_REF = "runless-proof-receipts"
RECEIPT_BASE = "devsystem/runless_proof_receipts"


class PostPurgeCloseoutFailure(RuntimeError):
    pass


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise PostPurgeCloseoutFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise PostPurgeCloseoutFailure(label + "_DECODE_FAILED") from exc


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


def _verify_step2a(client) -> tuple[dict[str, str], dict]:
    if client.branch_sha("main") != MAIN_SHA:
        raise PostPurgeCloseoutFailure("CLOSEOUT_MAIN_DRIFT")
    commit = client.commit(MAIN_SHA)
    parents = {str(item.get("sha") or "") for item in commit.get("parents", [])}
    if SOURCE_MAIN_SHA not in parents or SOURCE_CANDIDATE_SHA not in parents:
        raise PostPurgeCloseoutFailure("CLOSEOUT_MERGE_LINEAGE_DRIFT")

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    existing = (registry.get("entries") or {}).get(FREEZE_TOKEN)
    if str(registry.get("source_main_sha") or "") == MAIN_SHA and existing:
        return client.tree_blobs(MAIN_SHA), registry
    if str(registry.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        raise PostPurgeCloseoutFailure("REGISTRY_SOURCE_MAIN_DRIFT")
    if int(registry.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise PostPurgeCloseoutFailure("REGISTRY_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise PostPurgeCloseoutFailure("REGISTRY_HASH_DRIFT")

    old_tree = client.tree_blobs(SOURCE_MAIN_SHA)
    merged_tree = client.tree_blobs(MAIN_SHA)
    frozen_paths = {
        path
        for entry in (registry.get("entries") or {}).values()
        for path in (entry.get("artifacts") or {})
    }
    changed_frozen = sorted(
        path for path in frozen_paths
        if str(old_tree.get(path) or "") != str(merged_tree.get(path) or "")
    )
    if changed_frozen:
        raise PostPurgeCloseoutFailure(
            "EXISTING_FROZEN_DELTA:" + ",".join(changed_frozen[:20])
        )
    return merged_tree, registry


def _load_premerge_receipt(client) -> dict:
    raw = client.content(
        f"{RECEIPT_BASE}/{PREMERGE_PROOF_ID}.json",
        ref=RECEIPT_REF,
    )
    receipt = _decode_json(raw, "PREMERGE_RECEIPT")
    validate_runless_receipt(receipt)
    if str(receipt.get("proof_id") or "") != PREMERGE_PROOF_ID:
        raise PostPurgeCloseoutFailure("PREMERGE_PROOF_ID_DRIFT")
    if str(receipt.get("candidate_sha") or "") != SOURCE_CANDIDATE_SHA:
        raise PostPurgeCloseoutFailure("PREMERGE_CANDIDATE_DRIFT")
    if str(receipt.get("digest") or "") != PREMERGE_DIGEST:
        raise PostPurgeCloseoutFailure("PREMERGE_DIGEST_DRIFT")
    if str(receipt.get("failure_class") or "") != "NONE":
        raise PostPurgeCloseoutFailure("PREMERGE_NOT_GREEN")
    return receipt


def _ensure_merged_receipt_and_gate(
    client, *, tree: dict[str, str], premerge: dict, registry: dict
) -> dict:
    candidate_plan = _decode_json(
        client.content(PLAN_PATH, ref=SOURCE_CANDIDATE_SHA), "CANDIDATE_PLAN"
    )
    merged_plan = _decode_json(
        client.content(PLAN_PATH, ref=MAIN_SHA), "MERGED_PLAN"
    )
    candidate_tree = client.tree_blobs(SOURCE_CANDIDATE_SHA)
    candidate_artifacts = {
        path: str(candidate_tree.get(path) or "") for path in premerge["artifact_map"]
    }
    candidate_dependencies = {
        path: str(candidate_tree.get(path) or "") for path in premerge["dependency_map"]
    }
    merged_artifacts = {
        path: str(tree.get(path) or "") for path in premerge["artifact_map"]
    }
    merged_dependencies = {
        path: str(tree.get(path) or "") for path in premerge["dependency_map"]
    }
    if candidate_artifacts != dict(premerge.get("artifact_map") or {}):
        raise PostPurgeCloseoutFailure("CANDIDATE_ARTIFACT_RECEIPT_DRIFT")
    if candidate_dependencies != dict(premerge.get("dependency_map") or {}):
        raise PostPurgeCloseoutFailure("CANDIDATE_DEPENDENCY_RECEIPT_DRIFT")

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
        raise PostPurgeCloseoutFailure(
            "POSTMERGE_REUSE_REJECTED:" + ",".join(reuse.get("reasons") or [])
        )
    if reuse.get("static_evidence_reexecuted") is not False:
        raise PostPurgeCloseoutFailure("STATIC_EVIDENCE_REEXECUTION_DETECTED")
    if reuse.get("github_actions_enabled") is not False:
        raise PostPurgeCloseoutFailure("ACTIONS_FALLBACK_DETECTED")

    path = f"{RECEIPT_BASE}/{MERGED_PROOF_ID}.json"
    existing = client.content(path, ref=RECEIPT_REF, allow_404=True)
    if existing:
        merged = _decode_json(existing, "MERGED_RECEIPT")
        validate_runless_receipt(merged)
    else:
        merged = build_runless_receipt(
            proof_id=MERGED_PROOF_ID,
            task_id=str(premerge.get("task_id") or ""),
            project="API2",
            workstream=WORKSTREAM,
            step="games-on-this-day-step1-post-purge-closeout",
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
            "runless: persist CFB Games on This Day Step 1 post-purge merged receipt",
        )
    if str(merged.get("candidate_sha") or "") != MAIN_SHA:
        raise PostPurgeCloseoutFailure("MERGED_RECEIPT_MAIN_DRIFT")
    if str(merged.get("prior_digest") or "") != PREMERGE_DIGEST:
        raise PostPurgeCloseoutFailure("MERGED_RECEIPT_PRIOR_DRIFT")

    runs = client.request(
        "GET",
        f"/commits/{MAIN_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    expected_summary = "receipt=" + str(merged["digest"])
    gate_published = True
    for run in runs.get("check_runs", []):
        output = run.get("output") or {}
        if (
            str(run.get("head_sha") or "") == MAIN_SHA
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
            and str(output.get("summary") or "") == expected_summary
        ):
            gate_published = False
            break
    if gate_published:
        publish_gate(client, MAIN_SHA, "success", merged)
    return {
        "receipt": merged,
        "reuse": reuse,
        "gate_published": gate_published,
    }


def _freeze(client, *, tree: dict[str, str], premerge: dict) -> dict:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    entries = registry.get("entries") or {}
    freeze_artifacts = {
        path: str(tree.get(path) or "") for path in premerge["artifact_map"]
    }
    if any(not blob for blob in freeze_artifacts.values()):
        raise PostPurgeCloseoutFailure("FREEZE_ARTIFACT_MISSING")
    exact_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(sorted(freeze_artifacts.items())),
    }
    existing = entries.get(FREEZE_TOKEN)
    if str(registry.get("source_main_sha") or "") == MAIN_SHA and existing:
        if existing != exact_entry:
            raise PostPurgeCloseoutFailure("FREEZE_TOKEN_COLLISION")
        return {
            "already_frozen": True,
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
            "artifact_count": len(freeze_artifacts),
        }
    if str(registry.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        raise PostPurgeCloseoutFailure("FREEZE_REGISTRY_SOURCE_DRIFT")
    if int(registry.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise PostPurgeCloseoutFailure("FREEZE_REGISTRY_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise PostPurgeCloseoutFailure("FREEZE_REGISTRY_HASH_DRIFT")
    if client.branch_sha("main") != MAIN_SHA:
        raise PostPurgeCloseoutFailure("MAIN_MOVED_BEFORE_FREEZE")

    thaws_before = deepcopy(list(registry.get("active_thaws") or []))
    updated = deepcopy(registry)
    updated["entries"][FREEZE_TOKEN] = exact_entry
    updated["source_main_sha"] = MAIN_SHA
    updated["revision"] = int(registry["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)

    if client.branch_sha("main") != MAIN_SHA:
        raise PostPurgeCloseoutFailure("MAIN_MOVED_DURING_FREEZE")
    client.update_content(
        REGISTRY_PATH,
        _json_text(updated),
        backend.branch,
        "registry: freeze CFB Games on This Day Step 1 post-purge closeout",
        backend._blob_sha,
    )
    readback = backend.read_registry()
    validate_registry(readback)
    if str(readback.get("source_main_sha") or "") != MAIN_SHA:
        raise PostPurgeCloseoutFailure("FREEZE_READBACK_MAIN_DRIFT")
    if (readback.get("entries") or {}).get(FREEZE_TOKEN) != exact_entry:
        raise PostPurgeCloseoutFailure("FREEZE_READBACK_MISMATCH")
    if readback.get("active_thaws", []) != thaws_before:
        raise PostPurgeCloseoutFailure("UNRELATED_THAW_READBACK_DRIFT")
    if client.branch_sha("main") != MAIN_SHA:
        raise PostPurgeCloseoutFailure("MAIN_MOVED_AFTER_FREEZE")
    return {
        "already_frozen": False,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "artifact_count": len(freeze_artifacts),
        "unrelated_thaws_preserved": len(thaws_before),
    }


def _release_lease(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_lease_state(_decode_json(raw, "LEASE"))
    matches = [
        holder for holder in state.get("holders", [])
        if holder.get("lease_id") == LEASE_ID and holder.get("owner_id") == LEASE_OWNER
    ]
    if not matches:
        return {"released": False, "already_absent": True}
    if len(matches) != 1:
        raise PostPurgeCloseoutFailure("LEASE_IDENTITY_DRIFT")
    released = release_scope(
        state,
        owner_id=LEASE_OWNER,
        lease_id=LEASE_ID,
        expected_revision=int(state["revision"]),
        expected_state_hash=str(state["state_hash"]),
    )
    if released["result"].get("allowed") is not True:
        raise PostPurgeCloseoutFailure(
            "LEASE_RELEASE_BLOCKED:" + str(released["result"].get("decision") or "UNKNOWN")
        )
    client.update_content(
        LEASE_PATH,
        _json_text(released["state"]),
        LEASE_BRANCH,
        "lease: release CFB Games on This Day Step 1 post-purge scope",
        raw["sha"],
    )
    verify = validate_scope_lease_state(
        _decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "LEASE_READBACK")
    )
    if any(holder.get("lease_id") == LEASE_ID for holder in verify.get("holders", [])):
        raise PostPurgeCloseoutFailure("LEASE_RELEASE_READBACK_MISMATCH")
    return {
        "released": True,
        "state_hash": str(verify["state_hash"]),
        "remaining_holders": len(verify.get("holders", [])),
    }


def execute(app):
    client = app.state.github_client
    tree, registry = _verify_step2a(client)
    premerge = _load_premerge_receipt(client)
    merged = _ensure_merged_receipt_and_gate(
        client, tree=tree, premerge=premerge, registry=registry
    )
    frozen = _freeze(client, tree=tree, premerge=premerge)
    lease = _release_lease(client)
    if client.branch_sha("main") != MAIN_SHA:
        raise PostPurgeCloseoutFailure("MAIN_MOVED_AFTER_CLOSEOUT")
    return {
        "status": "GREEN",
        "decision": "CFB_GAMES_ON_DAY_STEP1_POST_PURGE_GREEN_FROZEN",
        "main_sha": MAIN_SHA,
        "source_candidate_sha": SOURCE_CANDIDATE_SHA,
        "premerge_check_id": PREMERGE_CHECK_ID,
        "premerge_receipt_digest": PREMERGE_DIGEST,
        "merged_receipt_digest": str(merged["receipt"]["digest"]),
        "freeze_token": FREEZE_TOKEN,
        "freeze": frozen,
        "lease": lease,
        "static_evidence_reexecuted": False,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_games_on_day_step1_post_purge_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step1_post_purge_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step1_post_purge_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:3200],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP1_POST_PURGE_CLOSEOUT="
            + json.dumps(
                app.state.cfb_games_on_day_step1_post_purge_closeout,
                sort_keys=True,
                default=str,
            ),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
