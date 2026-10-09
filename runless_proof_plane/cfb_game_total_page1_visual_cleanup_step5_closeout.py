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

TASK_ID = "cfb-game-total-page1-visual-cleanup-step5-live-visual-cert"
WORKSTREAM = "cfb-game-total-page1-visual-cleanup-v1"
SOURCE_MAIN_SHA = "0e2c11f03c1d3f6cb94756057ccb95e8ae74b2f9"
CANDIDATE_SHA = "f93fc641e50643f9b657bc2248b8254c8467dac2"
MERGED_MAIN_SHA = "5c155c494cf4e10148ebb3d6133d83a0ef42172c"
PR_NUMBER = 1483
PREMERGE_PROOF_ID = "cfb-game-total-page1-visual-cleanup-step5-live-visual-cert-f93fc641e50643f9-c5096752c298c9dc"
PREMERGE_DIGEST = "88a74b0f2575023a37446721c8fa3a35897c1f48d2a7f2fa7836f48e54d26e0b"
PREMERGE_CHECK_ID = 113951598329
CHECK_APP_ID = 5204253
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_V1_STEP5_LIVE_VISUAL_CERT_FROZEN"
POSTMERGE_PROOF_ID = TASK_ID + "-" + MERGED_MAIN_SHA[:16] + "-postmerge-reuse"

THAW_ID = "THAW-CFB-GT-P1-VISUAL-CLEANUP-STEP5-V191-ACTIVATION"
THAW_PATH = "streamlit_memory_lazy_router_v191.py"
THAW_FROM_BLOB = "1a4a2df127a060519d62ed96dd39f6c14bb79449"
THAW_TO_BLOB = "6f3b7132c75c360fd4d74c06e5e5b435435950f7"
V191_CHECKPOINT = "CFB_GAME_TOTAL_PAGE1_V2_STEP4_PUBLIC_RUNTIME_REPAIR_FROZEN"

REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
EXPECTED_REGISTRY_REVISION = 221
EXPECTED_REGISTRY_HASH = "acbe369a22b2dd4703be0344eb4838862fccc33b71aeeaaca0190385f5698763"
EXPECTED_UNRELATED_THAWS = (
    "THAW-NBA-OU-STEP2-BOOTSTRAP-R3",
    "THAW-RUNLESS-TASK14-MANUAL-FALLBACK",
)

LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2-cfb-game-total-page1-visual-cleanup-step5-convergence"
LEASE_ID = "SCOPE-LEASE-B255E6B5C7A6A1D05F969372"
RECEIPT_BRANCH = "runless-proof-receipts"
RECEIPT_DIR = "devsystem/runless_proof_receipts"
PREMERGE_RECEIPT_PATH = f"{RECEIPT_DIR}/{PREMERGE_PROOF_ID}.json"
POSTMERGE_RECEIPT_PATH = f"{RECEIPT_DIR}/{POSTMERGE_PROOF_ID}.json"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert.json"
EVIDENCE_BRANCH = "api2/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert"
EVIDENCE_PATH = "devsystem/live_evidence/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert.json"
EXPECTED_VIEWPORTS = {"mobile", "tablet", "desktop"}


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
    state = validate_scope_lease_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "STEP5_CLOSEOUT_LEASE"))
    now = datetime.now(timezone.utc)
    matches = [
        item for item in state.get("holders", [])
        if item.get("owner_id") == LEASE_OWNER
        and item.get("lease_id") == LEASE_ID
        and now < _utc(item["expires_at_utc"])
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
        or str(identity.get("registry_state_hash") or "") != EXPECTED_REGISTRY_HASH
    ):
        raise RuntimeError("STEP5_CLOSEOUT_LEASE_IDENTITY_DRIFT")
    required = {
        REGISTRY_PATH,
        EVIDENCE_PATH,
        "runless_proof_plane/cfb_game_total_page1_visual_cleanup_step5_closeout.py",
        "runless_proof_plane/nfl_rb_wr_step3_closeout.py",
    }
    if not required.issubset(set(scope.get("write_paths") or [])):
        raise RuntimeError("STEP5_CLOSEOUT_LEASE_SCOPE_DRIFT")
    return holder


def _premerge_receipt(client) -> dict:
    receipt = _decode_json(client.content(PREMERGE_RECEIPT_PATH, ref=RECEIPT_BRANCH), "STEP5_PREMERGE_RECEIPT")
    validate_runless_receipt(receipt)
    if (
        str(receipt.get("proof_id") or "") != PREMERGE_PROOF_ID
        or str(receipt.get("task_id") or "") != TASK_ID
        or str(receipt.get("workstream") or "") != WORKSTREAM
        or str(receipt.get("candidate_sha") or "") != CANDIDATE_SHA
        or str(receipt.get("digest") or "") != PREMERGE_DIGEST
        or str(receipt.get("failure_class") or "") != "NONE"
    ):
        raise RuntimeError("STEP5_PREMERGE_RECEIPT_IDENTITY_DRIFT")
    return receipt


def _premerge_gate(client) -> dict:
    runs = client.request("GET", f"/commits/{CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100") or {}
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
    raise RuntimeError("STEP5_PREMERGE_GATE_DRIFT")


def _merge_identity(client) -> dict:
    if client.branch_sha("main") != MERGED_MAIN_SHA:
        raise RuntimeError("STEP5_MERGED_MAIN_DRIFT")
    pr = client.request("GET", f"/pulls/{PR_NUMBER}") or {}
    if (
        not pr.get("merged_at")
        or str((pr.get("head") or {}).get("sha") or "") != CANDIDATE_SHA
        or str((pr.get("base") or {}).get("sha") or "") != SOURCE_MAIN_SHA
        or str(pr.get("merge_commit_sha") or "") != MERGED_MAIN_SHA
    ):
        raise RuntimeError("STEP5_MERGE_PROVENANCE_DRIFT")
    commit = client.commit(MERGED_MAIN_SHA)
    parents = {str(item.get("sha") or "") for item in commit.get("parents", [])}
    if CANDIDATE_SHA not in parents or SOURCE_MAIN_SHA not in parents:
        raise RuntimeError("STEP5_MERGE_LINEAGE_DRIFT")
    return {"parents": sorted(parents)}


def _live_evidence(client) -> tuple[dict, str]:
    raw = client.content(EVIDENCE_PATH, ref=EVIDENCE_BRANCH)
    evidence = _decode_json(raw, "STEP5_LIVE_EVIDENCE")
    if (
        str(evidence.get("status") or "") != "GREEN"
        or str(evidence.get("source_main_sha") or "") != SOURCE_MAIN_SHA
        or str(evidence.get("certified_merged_main_sha") or "") != MERGED_MAIN_SHA
        or str(evidence.get("phoenix_timezone") or "") != "America/Phoenix"
        or float(evidence.get("sportsbook_projection_influence", -1)) != 0.0
        or int(evidence.get("github_actions_fallback", -1)) != 0
    ):
        raise RuntimeError("STEP5_LIVE_EVIDENCE_IDENTITY_DRIFT")
    rows = evidence.get("viewports") or {}
    if set(rows) != EXPECTED_VIEWPORTS:
        raise RuntimeError("STEP5_LIVE_EVIDENCE_VIEWPORT_SET_DRIFT")
    for name in EXPECTED_VIEWPORTS:
        row = rows.get(name) or {}
        if (
            row.get("all_required_visible") is not True
            or row.get("phoenix_today_visible") is not True
            or row.get("friday_visible") is not True
            or int(row.get("games_on_day_surface_count", 0)) != 1
            or row.get("horizontal_overflow") is not False
            or row.get("forbidden_visible_text") not in ([], None)
            or str(row.get("runtime_error") or "")
        ):
            raise RuntimeError("STEP5_LIVE_EVIDENCE_VIEWPORT_DRIFT:" + name)
    return evidence, str(raw.get("sha") or "")


def _policy(client, ref: str) -> dict:
    plan = _decode_json(client.content(PLAN_PATH, ref=ref), "STEP5_PROOF_PLAN")
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
        raise RuntimeError("STEP5_POSTMERGE_ARTIFACT_DRIFT")
    if merged_dependencies != candidate_dependencies:
        raise RuntimeError("STEP5_POSTMERGE_DEPENDENCY_DRIFT")
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
        raise RuntimeError("STEP5_POSTMERGE_REUSE_REJECTED:" + ",".join(result.get("reasons") or []))
    if result.get("static_evidence_reexecuted") is not False:
        raise RuntimeError("STEP5_STATIC_EVIDENCE_REEXECUTED")
    return result


def _postmerge_receipt_payload(receipt: dict, gate: dict, reuse: dict, evidence: dict, evidence_sha: str) -> dict:
    payload = {
        "version": "CFB_GT_PAGE1_VISUAL_CLEANUP_STEP5_POSTMERGE_REUSE_V1",
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
        "live_visual_evidence_blob_sha": evidence_sha,
        "live_visual_evidence_digest": digest_payload(evidence),
        "live_visual_viewports": sorted(EXPECTED_VIEWPORTS),
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
            "runless: persist CFB Game Total Step5 postmerge reuse receipt",
        )
    stored = _decode_json(client.content(POSTMERGE_RECEIPT_PATH, ref=RECEIPT_BRANCH), "STEP5_POSTMERGE_RECEIPT")
    if stored != payload or str(stored.get("digest") or "") != digest_payload(stored):
        raise RuntimeError("STEP5_POSTMERGE_RECEIPT_DRIFT")
    return stored


def _merged_gate(client, digest: str) -> dict | None:
    runs = client.request("GET", f"/commits/{MERGED_MAIN_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100") or {}
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
        raise RuntimeError("STEP5_MERGED_GATE_READBACK_FAILED")
    return result


def _freeze_artifact_map(receipt: dict) -> dict:
    artifacts = dict(receipt.get("artifact_map") or {})
    artifacts[THAW_PATH] = THAW_TO_BLOB
    return artifacts


def _freeze_readback(client, artifact_map: dict) -> dict:
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    current = _decode_json(raw, "STEP5_REGISTRY")
    validate_registry(current)
    existing = (current.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is None:
        if (
            int(current.get("revision", -1)) != EXPECTED_REGISTRY_REVISION
            or str(current.get("state_hash") or "") != EXPECTED_REGISTRY_HASH
            or str(current.get("source_main_sha") or "") != SOURCE_MAIN_SHA
        ):
            raise RuntimeError("STEP5_REGISTRY_BASELINE_DRIFT")
        grant = next((item for item in current.get("active_thaws", []) if item.get("thaw_id") == THAW_ID), None)
        expected_grant = {
            "thaw_id": THAW_ID,
            "status": "ACTIVE",
            "target_head_sha": CANDIDATE_SHA,
            "files": {THAW_PATH: {"from_blob": THAW_FROM_BLOB, "to_blob": THAW_TO_BLOB}},
        }
        if grant != expected_grant:
            raise RuntimeError("STEP5_THAW_DRIFT")
        unrelated = [deepcopy(item) for item in current.get("active_thaws", []) if item.get("thaw_id") != THAW_ID]
        if tuple(sorted(str(item.get("thaw_id") or "") for item in unrelated)) != tuple(sorted(EXPECTED_UNRELATED_THAWS)):
            raise RuntimeError("STEP5_UNRELATED_THAW_SET_DRIFT")
        lifecycle = plan_baseline_forward_port(
            current,
            updates={THAW_PATH: {"from_blob": THAW_FROM_BLOB, "to_blob": THAW_TO_BLOB}},
            source_main_sha=MERGED_MAIN_SHA,
        )
        updated = lifecycle["registry"]
        if updated.get("active_thaws") != unrelated:
            raise RuntimeError("STEP5_UNRELATED_THAW_CONTENT_DRIFT")
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
            "registry: freeze CFB Game Total visual cleanup Step5",
            raw["sha"],
        )

    readback = _decode_json(client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH), "STEP5_REGISTRY_READBACK")
    validated = validate_registry(readback)
    frozen = (readback.get("entries") or {}).get(FREEZE_TOKEN)
    if (
        frozen is None
        or frozen.get("status") != "FROZEN"
        or str(frozen.get("source_main_sha") or "") != MERGED_MAIN_SHA
        or frozen.get("artifacts") != artifact_map
    ):
        raise RuntimeError("STEP5_FREEZE_READBACK_DRIFT")
    if str(readback.get("source_main_sha") or "") != MERGED_MAIN_SHA:
        raise RuntimeError("STEP5_REGISTRY_MAIN_READBACK_DRIFT")
    if any(item.get("thaw_id") == THAW_ID for item in readback.get("active_thaws", [])):
        raise RuntimeError("STEP5_THAW_NOT_RETIRED")
    if tuple(sorted(str(item.get("thaw_id") or "") for item in readback.get("active_thaws", []))) != tuple(sorted(EXPECTED_UNRELATED_THAWS)):
        raise RuntimeError("STEP5_UNRELATED_THAW_READBACK_DRIFT")
    owner = (readback.get("entries") or {}).get(V191_CHECKPOINT) or {}
    if str((owner.get("artifacts") or {}).get(THAW_PATH) or "") != THAW_TO_BLOB:
        raise RuntimeError("STEP5_BASELINE_FORWARD_PORT_READBACK_DRIFT")
    return {
        "revision": int(readback["revision"]),
        "state_hash": str(validated["state_hash"]),
        "active_thaw_count": len(readback.get("active_thaws") or []),
        "freeze_token": FREEZE_TOKEN,
    }


def should_run(client) -> bool:
    try:
        return _live_lease(client) is not None and client.branch_sha("main") == MERGED_MAIN_SHA and client.content(EVIDENCE_PATH, ref=EVIDENCE_BRANCH, allow_404=True) is not None
    except Exception:
        return False


def execute(app) -> dict:
    client = app.state.github_client
    if _live_lease(client) is None:
        raise RuntimeError("STEP5_CLOSEOUT_LEASE_NOT_LIVE")
    evidence, evidence_sha = _live_evidence(client)
    receipt = _premerge_receipt(client)
    gate = _premerge_gate(client)
    reuse = _evaluate_reuse(client, receipt)
    post = _persist_postmerge_receipt(client, _postmerge_receipt_payload(receipt, gate, reuse, evidence, evidence_sha))
    merged_gate = _publish_merged_gate(client, str(post["digest"]))
    artifacts = _freeze_artifact_map(receipt)
    freeze = _freeze_readback(client, artifacts)
    return {
        "status": "GREEN",
        "decision": "CFB_GT_STEP5_GREEN_FROZEN",
        "candidate_sha": CANDIDATE_SHA,
        "merged_main_sha": MERGED_MAIN_SHA,
        "premerge_receipt_digest": PREMERGE_DIGEST,
        "postmerge_receipt_digest": str(post["digest"]),
        "postmerge_reuse": "REUSE_APPROVED",
        "static_evidence_reexecuted": False,
        "live_visual_evidence_blob_sha": evidence_sha,
        "merged_gate_check_id": merged_gate["id"],
        "freeze_token": FREEZE_TOKEN,
        "registry_revision": freeze["revision"],
        "registry_state_hash": freeze["state_hash"],
        "active_thaw_count": freeze["active_thaw_count"],
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_visual_cleanup_step5_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if not should_run(app.state.github_client):
            return
        try:
            app.state.cfb_game_total_visual_cleanup_step5_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_visual_cleanup_step5_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:2200],
            }
        print(
            "CFB_GT_VISUAL_CLEANUP_STEP5_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_visual_cleanup_step5_closeout, sort_keys=True),
            flush=True,
        )

    return app
