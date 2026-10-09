from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import _hash as frozen_hash
from devsystem.frozen_artifact_registry_v1 import _payload_without_hash, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import (
    build_runless_receipt,
    digest_payload,
    validate_runless_receipt,
)
from devsystem.scope_aware_execution_lease_v1 import (
    release_scope,
    validate_state as validate_lease_state,
)
from .gate import publish_gate

MAIN_SHA = "337e9f2429aee703e821b226cc46ea3b52567986"
REPAIR_HEAD_SHA = "ba1caf4f1383e5169a1661cab1f5b78ed5c4c757"
REPAIR_PR = 1485
REPAIR_GATE_ID = 114015156271
REPAIR_DIGEST = "c256b2857f851695de03ec0190dcdeb9bf241ba06ce05dc408781dfba1041322"
CHECK_APP_ID = 5204253
WORKSTREAM = "cfb-game-total-page1-visual-cleanup-v1"
TASK_ID = "cfb-game-total-page1-visual-cleanup-step5-live-visual-cert"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_V1_STEP5_LIVE_VISUAL_CERT_FROZEN"
V191_PATH = "streamlit_memory_lazy_router_v191.py"
V191_OLD_BLOB = "1a4a2df127a060519d62ed96dd39f6c14bb79449"
V191_NEW_BLOB = "f256c6e2533c27b4710de63721a019f49db253f9"
THAW_ID = "THAW-CFB-GT-P1-VISUAL-CLEANUP-STEP5-V191-ACTIVATION"

EVIDENCE_BRANCH = "api2/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert"
EVIDENCE_PATH = "devsystem/live_evidence/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert.json"
EVIDENCE_BLOB = "3d92387a17478ac205e64fc5255be6b96e1912cc"

RECEIPT_BRANCH = "runless-proof-receipts"
REPAIR_RECEIPT_PATH = "devsystem/runless_proof_receipts/cfb-game-total-page1-visual-cleanup-step5-v191-idempotence-ba1caf4f1383e516.json"
FINAL_PROOF_ID = TASK_ID + "-" + MAIN_SHA[:16] + "-final"
FINAL_RECEIPT_PATH = f"devsystem/runless_proof_receipts/{FINAL_PROOF_ID}.json"

REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2-cfb-game-total-page1-visual-cleanup-step5-convergence"
LEASE_ID = "SCOPE-LEASE-1363371DFE615B06589A63D4"


def _decode(raw, label):
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(label + "_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode("utf-8"))


def _gate(client, sha, *, check_id=None, digest=None):
    runs = client.request(
        "GET",
        f"/commits/{sha}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    for run in runs.get("check_runs", []):
        app = run.get("app") or {}
        output = run.get("output") or {}
        if (
            str(run.get("head_sha") or "") == sha
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
            and int(app.get("id") or 0) == CHECK_APP_ID
            and (check_id is None or int(run.get("id") or 0) == int(check_id))
            and (digest is None or str(output.get("summary") or "") == "receipt=" + digest)
        ):
            return run
    return None


def _terminal_inputs(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("STEP5_FINAL_MAIN_DRIFT")

    pr = client.request("GET", f"/pulls/{REPAIR_PR}") or {}
    if (
        not pr.get("merged_at")
        or str((pr.get("head") or {}).get("sha") or "") != REPAIR_HEAD_SHA
        or str(pr.get("merge_commit_sha") or "") != MAIN_SHA
    ):
        raise RuntimeError("STEP5_FINAL_REPAIR_MERGE_DRIFT")

    repair = _decode(client.content(REPAIR_RECEIPT_PATH, ref=RECEIPT_BRANCH), "STEP5_FINAL_REPAIR_RECEIPT")
    validate_runless_receipt(repair)
    if (
        str(repair.get("candidate_sha") or "") != REPAIR_HEAD_SHA
        or str(repair.get("digest") or "") != REPAIR_DIGEST
        or str(repair.get("failure_class") or "") != "NONE"
        or int(repair.get("github_actions_fallback", -1)) != 0
    ):
        raise RuntimeError("STEP5_FINAL_REPAIR_RECEIPT_DRIFT")
    if _gate(client, REPAIR_HEAD_SHA, check_id=REPAIR_GATE_ID, digest=REPAIR_DIGEST) is None:
        raise RuntimeError("STEP5_FINAL_REPAIR_GATE_DRIFT")

    artifacts = dict(repair.get("artifact_map") or {})
    dependencies = dict(repair.get("dependency_map") or {})
    if artifacts.get(V191_PATH) != V191_NEW_BLOB:
        raise RuntimeError("STEP5_FINAL_V191_RECEIPT_DRIFT")
    for path, blob in {**artifacts, **dependencies}.items():
        raw = client.content(path, ref=MAIN_SHA)
        if str(raw.get("sha") or "") != str(blob):
            raise RuntimeError("STEP5_FINAL_MAIN_BLOB_DRIFT:" + path)

    evidence_raw = client.content(EVIDENCE_PATH, ref=EVIDENCE_BRANCH)
    if str(evidence_raw.get("sha") or "") != EVIDENCE_BLOB:
        raise RuntimeError("STEP5_FINAL_EVIDENCE_BLOB_DRIFT")
    evidence = _decode(evidence_raw, "STEP5_FINAL_EVIDENCE")
    if (
        evidence.get("status") != "GREEN"
        or str(evidence.get("source_main_sha") or "") != MAIN_SHA
        or str(evidence.get("certified_merged_main_sha") or "") != MAIN_SHA
        or str(evidence.get("phoenix_timezone") or "") != "America/Phoenix"
        or int(evidence.get("github_actions_fallback", -1)) != 0
    ):
        raise RuntimeError("STEP5_FINAL_EVIDENCE_IDENTITY_DRIFT")
    rows = evidence.get("viewports") or {}
    if set(rows) != {"mobile", "tablet", "desktop"}:
        raise RuntimeError("STEP5_FINAL_VIEWPORT_SET_DRIFT")
    for name, row in rows.items():
        if (
            row.get("all_required_visible") is not True
            or row.get("phoenix_today_visible") is not True
            or int(row.get("games_on_day_surface_count", 0)) != 1
            or row.get("horizontal_overflow") is not False
            or row.get("forbidden_visible_text") not in ([], None)
            or str(row.get("runtime_error") or "")
        ):
            raise RuntimeError("STEP5_FINAL_VIEWPORT_DRIFT:" + name)
    return repair, evidence, artifacts


def _registry_plan(client, artifacts):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    current = _decode(raw, "STEP5_FINAL_REGISTRY")
    validate_registry(current)
    existing = (current.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is not None:
        if (
            existing.get("status") != "FROZEN"
            or str(existing.get("source_main_sha") or "") != MAIN_SHA
            or existing.get("artifacts") != artifacts
        ):
            raise RuntimeError("STEP5_FINAL_EXISTING_FREEZE_DRIFT")
        return raw, current, current

    grant = next((x for x in current.get("active_thaws", []) if x.get("thaw_id") == THAW_ID), None)
    if grant is None:
        raise RuntimeError("STEP5_FINAL_THAW_MISSING")
    pair = (grant.get("files") or {}).get(V191_PATH) or {}
    if str(pair.get("from_blob") or "") != V191_OLD_BLOB:
        raise RuntimeError("STEP5_FINAL_THAW_BASE_DRIFT")
    unrelated = [deepcopy(x) for x in current.get("active_thaws", []) if x.get("thaw_id") != THAW_ID]

    lifecycle = plan_baseline_forward_port(
        current,
        updates={V191_PATH: {"from_blob": V191_OLD_BLOB, "to_blob": V191_NEW_BLOB}},
        source_main_sha=MAIN_SHA,
    )
    updated = lifecycle["registry"]
    if updated.get("active_thaws") != unrelated:
        raise RuntimeError("STEP5_FINAL_UNRELATED_THAW_DRIFT")
    updated["entries"][FREEZE_TOKEN] = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(artifacts),
    }
    updated["state_hash"] = frozen_hash(_payload_without_hash(updated))
    validate_registry(updated)
    return raw, current, updated


def _final_receipt(client, repair, evidence, before, after, artifacts):
    existing = client.content(FINAL_RECEIPT_PATH, ref=RECEIPT_BRANCH, allow_404=True)
    if existing is not None:
        receipt = _decode(existing, "STEP5_FINAL_RECEIPT")
        validate_runless_receipt(receipt)
        if (
            str(receipt.get("candidate_sha") or "") != MAIN_SHA
            or receipt.get("artifact_map") != artifacts
            or str(receipt.get("failure_class") or "") != "NONE"
        ):
            raise RuntimeError("STEP5_FINAL_RECEIPT_DRIFT")
        return receipt

    receipt = build_runless_receipt(
        proof_id=FINAL_PROOF_ID,
        task_id=TASK_ID,
        project="API2",
        workstream=WORKSTREAM,
        step="5/5-final",
        candidate_sha=MAIN_SHA,
        artifact_map=artifacts,
        dependency_map=dict(repair.get("dependency_map") or {}),
        registry_before={"revision": int(before["revision"]), "state_hash": str(before["state_hash"])},
        registry_after={"revision": int(after["revision"]), "state_hash": str(after["state_hash"])},
        evidence_digests={
            "live_visual_evidence": digest_payload(evidence),
            "repair_receipt": REPAIR_DIGEST,
        },
        failure_class="NONE",
        github_actions_fallback=0,
        scope_lease_id=LEASE_ID,
        authorization_id="FINALIZATION-AUTHORITY-CFB-GT-P1-STEP5-100P",
    )
    client.put_content(
        FINAL_RECEIPT_PATH,
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        RECEIPT_BRANCH,
        "runless: persist CFB Game Total Step5 final receipt",
    )
    stored = _decode(client.content(FINAL_RECEIPT_PATH, ref=RECEIPT_BRANCH), "STEP5_FINAL_RECEIPT")
    if stored != receipt:
        raise RuntimeError("STEP5_FINAL_RECEIPT_READBACK_DRIFT")
    return stored


def _freeze(client, raw, planned, artifacts):
    current = _decode(client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH), "STEP5_FINAL_REGISTRY_REREAD")
    existing = (current.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is None:
        if str(current.get("state_hash") or "") != str(_decode(raw, "STEP5_FINAL_REGISTRY_BASE")["state_hash"]):
            raise RuntimeError("STEP5_FINAL_REGISTRY_CAS_DRIFT")
        client.update_content(
            REGISTRY_PATH,
            json.dumps(planned, indent=2, sort_keys=True) + "\n",
            REGISTRY_BRANCH,
            "registry: freeze CFB Game Total Page1 visual cleanup Step5",
            raw["sha"],
        )
    readback = _decode(client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH), "STEP5_FINAL_REGISTRY_READBACK")
    validate_registry(readback)
    frozen = (readback.get("entries") or {}).get(FREEZE_TOKEN) or {}
    if (
        frozen.get("status") != "FROZEN"
        or str(frozen.get("source_main_sha") or "") != MAIN_SHA
        or frozen.get("artifacts") != artifacts
        or any(x.get("thaw_id") == THAW_ID for x in readback.get("active_thaws", []))
    ):
        raise RuntimeError("STEP5_FINAL_FREEZE_READBACK_DRIFT")
    return readback


def _release(client):
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_lease_state(_decode(raw, "STEP5_FINAL_LEASE"))
    holder = next(
        (h for h in state.get("holders", []) if h.get("owner_id") == LEASE_OWNER and h.get("lease_id") == LEASE_ID),
        None,
    )
    if holder is not None:
        identity = (holder.get("scope") or {}).get("resource_identity") or {}
        if str(identity.get("main_sha") or "") != MAIN_SHA:
            raise RuntimeError("STEP5_FINAL_LEASE_IDENTITY_DRIFT")
        released = release_scope(
            state,
            owner_id=LEASE_OWNER,
            lease_id=LEASE_ID,
            expected_revision=int(state["revision"]),
            expected_state_hash=str(state["state_hash"]),
        )
        if released["result"].get("decision") != "SCOPE_LEASE_RELEASED":
            raise RuntimeError("STEP5_FINAL_LEASE_RELEASE_FAILED")
        client.update_content(
            LEASE_PATH,
            json.dumps(released["state"], indent=2, sort_keys=True) + "\n",
            LEASE_BRANCH,
            "lease: release CFB Game Total Step5 finalization",
            raw["sha"],
        )
    readback = validate_lease_state(_decode(client.content(LEASE_PATH, ref=LEASE_BRANCH), "STEP5_FINAL_LEASE_READBACK"))
    if any(h.get("lease_id") == LEASE_ID for h in readback.get("holders", [])):
        raise RuntimeError("STEP5_FINAL_LEASE_STILL_HELD")
    return readback


def execute(app):
    client = app.state.github_client
    repair, evidence, artifacts = _terminal_inputs(client)
    reg_raw, before, planned = _registry_plan(client, artifacts)

    lease_state = validate_lease_state(_decode(client.content(LEASE_PATH, ref=LEASE_BRANCH), "STEP5_FINAL_LEASE_PRECHECK"))
    holder = next((h for h in lease_state.get("holders", []) if h.get("lease_id") == LEASE_ID), None)
    already_frozen = (before.get("entries") or {}).get(FREEZE_TOKEN) is not None
    if holder is None and not already_frozen:
        raise RuntimeError("STEP5_FINAL_LEASE_NOT_HELD")

    receipt = _final_receipt(client, repair, evidence, before, planned, artifacts)
    registry = _freeze(client, reg_raw, planned, artifacts)

    gate = _gate(client, MAIN_SHA, digest=str(receipt["digest"]))
    if gate is None:
        publish_gate(client, MAIN_SHA, "success", receipt, "runless-final-gate")
        gate = _gate(client, MAIN_SHA, digest=str(receipt["digest"]))
    if gate is None:
        raise RuntimeError("STEP5_FINAL_GATE_READBACK_FAILED")

    lease = _release(client)
    return {
        "status": "GREEN",
        "decision": "CFB_GT_PAGE1_VISUAL_CLEANUP_STEP5_100_PERCENT_FROZEN",
        "main_sha": MAIN_SHA,
        "repair_head_sha": REPAIR_HEAD_SHA,
        "live_evidence_blob": EVIDENCE_BLOB,
        "final_receipt_digest": str(receipt["digest"]),
        "merged_gate_check_id": int(gate.get("id") or 0),
        "freeze_token": FREEZE_TOKEN,
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
        "lease_released": True,
        "remaining_lease_holders": len(lease.get("holders") or []),
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.nfl_rb_wr_step3_closeout = {"status": "NOT_RUN", "decision": "CFB_GT_STEP5_FINAL_ONLY"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.nfl_rb_wr_step3_closeout = execute(app)
        except Exception as exc:
            app.state.nfl_rb_wr_step3_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:2400],
            }
        print("CFB_GT_STEP5_FINAL=" + json.dumps(app.state.nfl_rb_wr_step3_closeout, sort_keys=True), flush=True)

    return app
