from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import _hash as frozen_hash
from devsystem.frozen_artifact_registry_v1 import _payload_without_hash, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import digest_payload, validate_runless_receipt
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state
from .postmerge_reuse import evaluate_postmerge_reuse

TASK_ID = "cfb-game-total-page1-visual-cleanup-step3-overview-team-snapshot"
WORKSTREAM = "cfb-game-total-page1-visual-cleanup-v1"
SOURCE_MAIN_SHA = "036dbb2ab3a0e24ce3e1cb16c1b2f9469cfce2f4"
CANDIDATE_SHA = "188b065e404141373c3f1157b7729243ef948e16"
MERGED_MAIN_SHA = "5c7373ecb1c5c042db0909cc9f7d9e6c64ba43ff"
PR_NUMBER = 1481
PREMERGE_PROOF_ID = "cfb-game-total-page1-visual-cleanup-step3-overview-team-snapshot-188b065e40414137-8025c95c89a29016"
PREMERGE_DIGEST = "e5370570cf8ba0b3c0ae5e1313d0f7ff1d211062074dcac2b5c905e7235dc5f4"
PREMERGE_CHECK_ID = 113898972457
CHECK_APP_ID = 5204253
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_V1_STEP3_OVERVIEW_TEAM_SNAPSHOT_FROZEN"
POSTMERGE_PROOF_ID = TASK_ID + "-" + MERGED_MAIN_SHA[:16] + "-postmerge-reuse"

THAW_ID = "THAW-CFB-GT-P1-VISUAL-CLEANUP-STEP3-OVERVIEW"
THAW_PATH = "cfb_game_total_page1_v2_step4_side_market_completeness_v1.py"
THAW_FROM_BLOB = "b52cd7497388dbfe01a921014e13f9d99202cb84"
THAW_TO_BLOB = "f8ec957d95a8ebc152996195b97f366da41beb59"
SIDE_MARKET_CHECKPOINT = "CFB_GAME_TOTAL_PAGE1_V2_STEP4_SIDE_MARKET_COMPLETENESS_FROZEN"

REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
EXPECTED_REGISTRY_REVISION = 215
EXPECTED_REGISTRY_HASH = "97fc2ecfa858e67e4ec94f9629671c83de227d8821f20bdb780dcc9a97171d4b"
EXPECTED_UNRELATED_THAWS = (
    "THAW-NBA-OU-STEP2-BOOTSTRAP-R3",
    "THAW-RUNLESS-TASK14-MANUAL-FALLBACK",
)

LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2-cfb-game-total-page1-visual-cleanup-step3-convergence"
RECEIPT_BRANCH = "runless-proof-receipts"
RECEIPT_DIR = "devsystem/runless_proof_receipts"
PREMERGE_RECEIPT_PATH = f"{RECEIPT_DIR}/{PREMERGE_PROOF_ID}.json"
POSTMERGE_RECEIPT_PATH = f"{RECEIPT_DIR}/{POSTMERGE_PROOF_ID}.json"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-page1-visual-cleanup-step3-overview-team-snapshot.json"


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise RuntimeError(label + "_DECODE_FAILED") from exc


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _live_lease(client) -> dict | None:
    state = validate_scope_lease_state(
        _decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "CFB_GT_STEP3_CLOSEOUT_LEASE")
    )
    now = datetime.now(timezone.utc)
    matches = [
        item for item in state.get("holders", [])
        if item.get("owner_id") == LEASE_OWNER and now < _utc(item["expires_at_utc"])
    ]
    if len(matches) != 1:
        return None
    holder = matches[0]
    scope = holder.get("scope") or {}
    identity = scope.get("resource_identity") or {}
    if (
        str(identity.get("candidate_sha") or "") != CANDIDATE_SHA
        or str(identity.get("main_sha") or "") != SOURCE_MAIN_SHA
        or str(identity.get("workstream") or "") != WORKSTREAM
        or str(identity.get("pr_number") or "") != str(PR_NUMBER)
        or str(identity.get("registry_state_hash") or "") != EXPECTED_REGISTRY_HASH
    ):
        raise RuntimeError("CFB_GT_STEP3_CLOSEOUT_LEASE_IDENTITY_DRIFT")
    required_paths = {
        REGISTRY_PATH,
        "runless_proof_plane/cfb_game_total_page1_visual_cleanup_step3_closeout.py",
        "runless_proof_plane/nfl_rb_wr_step3_closeout.py",
    }
    if not required_paths.issubset(set(scope.get("write_paths") or [])):
        raise RuntimeError("CFB_GT_STEP3_CLOSEOUT_LEASE_SCOPE_DRIFT")
    return holder


def _premerge_receipt(client) -> dict:
    receipt = _decode_json(
        client.content(PREMERGE_RECEIPT_PATH, ref=RECEIPT_BRANCH),
        "CFB_GT_STEP3_PREMERGE_RECEIPT",
    )
    validate_runless_receipt(receipt)
    if (
        str(receipt.get("proof_id") or "") != PREMERGE_PROOF_ID
        or str(receipt.get("task_id") or "") != TASK_ID
        or str(receipt.get("workstream") or "") != WORKSTREAM
        or str(receipt.get("candidate_sha") or "") != CANDIDATE_SHA
        or str(receipt.get("digest") or "") != PREMERGE_DIGEST
        or str(receipt.get("failure_class") or "") != "NONE"
    ):
        raise RuntimeError("CFB_GT_STEP3_PREMERGE_RECEIPT_IDENTITY_DRIFT")
    return receipt


def _premerge_gate(client) -> dict:
    runs = client.request(
        "GET",
        f"/commits/{CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    for run in runs.get("check_runs", []):
        app = run.get("app") or {}
        output = run.get("output") or {}
        if (
            int(run.get("id") or 0) == PREMERGE_CHECK_ID
            and str(run.get("head_sha") or "") == CANDIDATE_SHA
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
            and int(app.get("id") or 0) == CHECK_APP_ID
            and str(output.get("summary") or "") == "receipt=" + PREMERGE_DIGEST
        ):
            return {"id": PREMERGE_CHECK_ID, "receipt_digest": PREMERGE_DIGEST}
    raise RuntimeError("CFB_GT_STEP3_PREMERGE_GATE_DRIFT")


def _merge_identity(client) -> dict:
    if client.branch_sha("main") != MERGED_MAIN_SHA:
        raise RuntimeError("CFB_GT_STEP3_MERGED_MAIN_DRIFT")
    pr = client.request("GET", f"/pulls/{PR_NUMBER}") or {}
    if (
        not pr.get("merged_at")
        or str((pr.get("head") or {}).get("sha") or "") != CANDIDATE_SHA
        or str((pr.get("base") or {}).get("sha") or "") != SOURCE_MAIN_SHA
        or str(pr.get("merge_commit_sha") or "") != MERGED_MAIN_SHA
    ):
        raise RuntimeError("CFB_GT_STEP3_MERGE_PROVENANCE_DRIFT")
    commit = client.commit(MERGED_MAIN_SHA)
    parents = {str(item.get("sha") or "") for item in commit.get("parents", [])}
    if CANDIDATE_SHA not in parents or SOURCE_MAIN_SHA not in parents:
        raise RuntimeError("CFB_GT_STEP3_MERGE_LINEAGE_DRIFT")
    return {"parents": sorted(parents)}


def _policy(client, ref: str) -> dict:
    plan = _decode_json(client.content(PLAN_PATH, ref=ref), "CFB_GT_STEP3_PROOF_PLAN")
    return {
        "commands": list(plan.get("commands") or []),
        "probes": list(plan.get("probes") or []),
        "timeout_seconds": int(plan.get("timeout_seconds") or 0),
        "live_ttl_seconds": int(plan.get("live_ttl_seconds") or 0),
        "freeze_token": str(plan.get("freeze_token") or ""),
    }


def _evaluate_reuse(client, receipt: dict) -> dict:
    _merge_identity(client)
    candidate_artifacts = dict(receipt.get("artifact_map") or {})
    candidate_dependencies = dict(receipt.get("dependency_map") or {})
    main_tree = client.tree_blobs(MERGED_MAIN_SHA)
    merged_artifacts = {path: main_tree.get(path) for path in candidate_artifacts}
    merged_dependencies = {path: main_tree.get(path) for path in candidate_dependencies}
    if merged_artifacts != candidate_artifacts:
        raise RuntimeError("CFB_GT_STEP3_POSTMERGE_ARTIFACT_DRIFT")
    if merged_dependencies != candidate_dependencies:
        raise RuntimeError("CFB_GT_STEP3_POSTMERGE_DEPENDENCY_DRIFT")
    result = evaluate_postmerge_reuse(
        premerge_receipt=receipt,
        merged_main_sha=MERGED_MAIN_SHA,
        merged_artifacts=merged_artifacts,
        merged_dependencies=merged_dependencies,
        candidate_policy=_policy(client, CANDIDATE_SHA),
        merged_policy=_policy(client, MERGED_MAIN_SHA),
        candidate_is_ancestor=True,
        proof_run_id=PREMERGE_CHECK_ID,
    )
    if result.get("decision") != "REUSE_APPROVED" or result.get("reusable") is not True:
        raise RuntimeError("CFB_GT_STEP3_POSTMERGE_REUSE_REJECTED:" + ",".join(result.get("reasons") or []))
    if result.get("static_evidence_reexecuted") is not False:
        raise RuntimeError("CFB_GT_STEP3_STATIC_EVIDENCE_REEXECUTED")
    return result


def _postmerge_receipt_payload(receipt: dict, gate: dict, reuse: dict) -> dict:
    payload = {
        "version": "CFB_GT_PAGE1_VISUAL_CLEANUP_STEP3_POSTMERGE_REUSE_V1",
        "proof_id": POSTMERGE_PROOF_ID,
        "task_id": TASK_ID,
        "workstream": WORKSTREAM,
        "failure_class": "NONE",
        "proof_reuse_decision": "REUSE_APPROVED",
        "reusable": True,
        "source_candidate_sha": CANDIDATE_SHA,
        "merged_main_sha": MERGED_MAIN_SHA,
        "premerge_runless_proof_id": PREMERGE_PROOF_ID,
        "premerge_runless_receipt_digest": PREMERGE_DIGEST,
        "premerge_runless_gate_check_id": int(gate["id"]),
        "artifact_map": dict(receipt["artifact_map"]),
        "dependency_map": dict(receipt["dependency_map"]),
        "all_artifact_blobs_identical": True,
        "all_dependency_blobs_identical": True,
        "static_evidence_reexecuted": False,
        "github_actions_fallback": 0,
        "freeze_token": FREEZE_TOKEN,
        "content_fingerprint": str(reuse.get("content_fingerprint") or ""),
        "proof_policy_digest": str(reuse.get("proof_policy_digest") or ""),
        "proof_run_id": PREMERGE_CHECK_ID,
    }
    payload["digest"] = digest_payload(payload)
    return payload


def _persist_postmerge_receipt(client, payload: dict) -> dict:
    existing = client.content(POSTMERGE_RECEIPT_PATH, ref=RECEIPT_BRANCH, allow_404=True)
    if existing is None:
        client.put_content(
            POSTMERGE_RECEIPT_PATH,
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            RECEIPT_BRANCH,
            "runless: persist CFB Game Total Step3 postmerge reuse receipt",
        )
    stored = _decode_json(
        client.content(POSTMERGE_RECEIPT_PATH, ref=RECEIPT_BRANCH),
        "CFB_GT_STEP3_POSTMERGE_RECEIPT",
    )
    if stored != payload or str(stored.get("digest") or "") != digest_payload(stored):
        raise RuntimeError("CFB_GT_STEP3_POSTMERGE_RECEIPT_DRIFT")
    return stored


def _merged_gate(client, digest: str) -> dict | None:
    runs = client.request(
        "GET",
        f"/commits/{MERGED_MAIN_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    for run in runs.get("check_runs", []):
        app = run.get("app") or {}
        output = run.get("output") or {}
        if (
            str(run.get("head_sha") or "") == MERGED_MAIN_SHA
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
            and int(app.get("id") or 0) == CHECK_APP_ID
            and str(output.get("summary") or "") == "receipt=" + digest
        ):
            return {"id": int(run.get("id") or 0), "app_id": CHECK_APP_ID, "receipt_digest": digest}
    return None


def _publish_merged_gate(client, digest: str) -> dict:
    existing = _merged_gate(client, digest)
    if existing is not None:
        return existing
    client.publish_check(
        MERGED_MAIN_SHA,
        "runless-final-gate",
        "success",
        {"title": "Runless Proof Plane", "summary": "receipt=" + digest},
    )
    result = _merged_gate(client, digest)
    if result is None:
        raise RuntimeError("CFB_GT_STEP3_MERGED_GATE_READBACK_FAILED")
    return result


def _freeze_readback(client, artifact_map: dict) -> dict:
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    current = _decode_json(raw, "CFB_GT_STEP3_REGISTRY")
    validate_registry(current)
    existing = (current.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is None:
        if (
            int(current.get("revision", -1)) != EXPECTED_REGISTRY_REVISION
            or str(current.get("state_hash") or "") != EXPECTED_REGISTRY_HASH
            or str(current.get("source_main_sha") or "") != SOURCE_MAIN_SHA
        ):
            raise RuntimeError("CFB_GT_STEP3_REGISTRY_BASELINE_DRIFT")
        step3_grant = next(
            (item for item in current.get("active_thaws", []) if item.get("thaw_id") == THAW_ID),
            None,
        )
        expected_grant = {
            "thaw_id": THAW_ID,
            "status": "ACTIVE",
            "target_head_sha": CANDIDATE_SHA,
            "files": {THAW_PATH: {"from_blob": THAW_FROM_BLOB, "to_blob": THAW_TO_BLOB}},
        }
        if step3_grant != expected_grant:
            raise RuntimeError("CFB_GT_STEP3_THAW_DRIFT")
        unrelated = [deepcopy(item) for item in current.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
        if tuple(sorted(str(item.get("thaw_id") or "") for item in unrelated)) != tuple(sorted(EXPECTED_UNRELATED_THAWS)):
            raise RuntimeError("CFB_GT_STEP3_UNRELATED_THAW_SET_DRIFT")
        lifecycle = plan_baseline_forward_port(
            current,
            updates={THAW_PATH: {"from_blob": THAW_FROM_BLOB, "to_blob": THAW_TO_BLOB}},
            source_main_sha=MERGED_MAIN_SHA,
        )
        updated = lifecycle["registry"]
        if updated.get("active_thaws") != unrelated:
            raise RuntimeError("CFB_GT_STEP3_UNRELATED_THAW_CONTENT_DRIFT")
        updated["entries"][FREEZE_TOKEN] = {
            "status": "FROZEN",
            "checkpoint_id": FREEZE_TOKEN,
            "source_main_sha": MERGED_MAIN_SHA,
            "artifacts": dict(artifact_map),
        }
        updated["state_hash"] = frozen_hash(_payload_without_hash(updated))
        validate_registry(updated)
        client.update_content(
            REGISTRY_PATH,
            json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            REGISTRY_BRANCH,
            "registry: freeze CFB Game Total visual cleanup Step3",
            raw["sha"],
        )

    readback = _decode_json(
        client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH),
        "CFB_GT_STEP3_REGISTRY_READBACK",
    )
    validated = validate_registry(readback)
    frozen = (readback.get("entries") or {}).get(FREEZE_TOKEN)
    if (
        frozen is None
        or frozen.get("status") != "FROZEN"
        or str(frozen.get("source_main_sha") or "") != MERGED_MAIN_SHA
        or frozen.get("artifacts") != artifact_map
    ):
        raise RuntimeError("CFB_GT_STEP3_FREEZE_READBACK_DRIFT")
    if str(readback.get("source_main_sha") or "") != MERGED_MAIN_SHA:
        raise RuntimeError("CFB_GT_STEP3_REGISTRY_MAIN_READBACK_DRIFT")
    if any(item.get("thaw_id") == THAW_ID for item in readback.get("active_thaws", [])):
        raise RuntimeError("CFB_GT_STEP3_THAW_NOT_RETIRED")
    if tuple(sorted(str(item.get("thaw_id") or "") for item in readback.get("active_thaws", []))) != tuple(sorted(EXPECTED_UNRELATED_THAWS)):
        raise RuntimeError("CFB_GT_STEP3_UNRELATED_THAW_READBACK_DRIFT")
    owner = (readback.get("entries") or {}).get(SIDE_MARKET_CHECKPOINT) or {}
    if str((owner.get("artifacts") or {}).get(THAW_PATH) or "") != THAW_TO_BLOB:
        raise RuntimeError("CFB_GT_STEP3_BASELINE_FORWARD_PORT_READBACK_DRIFT")
    return {
        "revision": int(readback["revision"]),
        "state_hash": str(validated["state_hash"]),
        "active_thaw_count": len(readback.get("active_thaws") or []),
        "freeze_token": FREEZE_TOKEN,
    }


def should_run(client) -> bool:
    try:
        return _live_lease(client) is not None and client.branch_sha("main") == MERGED_MAIN_SHA
    except Exception:
        return False


def execute(app) -> dict:
    client = app.state.github_client
    if _live_lease(client) is None:
        raise RuntimeError("CFB_GT_STEP3_CLOSEOUT_LEASE_NOT_LIVE")
    receipt = _premerge_receipt(client)
    gate = _premerge_gate(client)
    reuse = _evaluate_reuse(client, receipt)
    post = _persist_postmerge_receipt(client, _postmerge_receipt_payload(receipt, gate, reuse))
    merged_gate = _publish_merged_gate(client, str(post["digest"]))
    freeze = _freeze_readback(client, dict(receipt["artifact_map"]))
    return {
        "status": "GREEN",
        "decision": "CFB_GT_STEP3_GREEN_FROZEN",
        "candidate_sha": CANDIDATE_SHA,
        "merged_main_sha": MERGED_MAIN_SHA,
        "premerge_receipt_digest": PREMERGE_DIGEST,
        "postmerge_receipt_digest": str(post["digest"]),
        "postmerge_reuse": "REUSE_APPROVED",
        "static_evidence_reexecuted": False,
        "merged_gate_check_id": merged_gate["id"],
        "freeze_token": FREEZE_TOKEN,
        "registry_revision": freeze["revision"],
        "registry_state_hash": freeze["state_hash"],
        "active_thaw_count": freeze["active_thaw_count"],
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_visual_cleanup_step3_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if not should_run(app.state.github_client):
            return
        try:
            app.state.cfb_game_total_visual_cleanup_step3_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_visual_cleanup_step3_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_VISUAL_CLEANUP_STEP3_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_visual_cleanup_step3_closeout, sort_keys=True),
            flush=True,
        )

    return app
