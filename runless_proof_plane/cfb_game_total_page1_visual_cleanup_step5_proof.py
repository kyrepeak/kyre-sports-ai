from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state
from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page1-visual-cleanup-step5-live-visual-cert"
WORKSTREAM = "cfb-game-total-page1-visual-cleanup-v1"
CANDIDATE_SHA = "f93fc641e50643f9b657bc2248b8254c8467dac2"
EXPECTED_MAIN_SHA = "0e2c11f03c1d3f6cb94756057ccb95e8ae74b2f9"
PR_NUMBER = 1483
LEASE_OWNER = "api2-cfb-game-total-page1-visual-cleanup-step5-convergence"
LEASE_ID = "SCOPE-LEASE-B255E6B5C7A6A1D05F969372"
AUTHORIZATION_ID = "AUTH-CFB-GT-P1-VISUAL-CLEANUP-STEP5-1483"
GATE_NAME = "runless-final-gate"
CHECK_APP_ID = 5204253
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"


def _decode(raw, label):
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(label + "_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _holder(client):
    state = validate_scope_lease_state(_decode(client.content(LEASE_PATH, ref=LEASE_BRANCH), "STEP5_PROOF_LEASE"))
    now = datetime.now(timezone.utc)
    matches = [
        h for h in state.get("holders", [])
        if h.get("owner_id") == LEASE_OWNER
        and h.get("lease_id") == LEASE_ID
        and now < _utc(h["expires_at_utc"])
    ]
    if len(matches) != 1:
        return None
    holder = matches[0]
    identity = (holder.get("scope") or {}).get("resource_identity") or {}
    if (
        str(identity.get("candidate_sha") or "") != CANDIDATE_SHA
        or str(identity.get("main_sha") or "") != EXPECTED_MAIN_SHA
        or str(identity.get("workstream") or "") != WORKSTREAM
    ):
        raise RuntimeError("STEP5_PROOF_LEASE_IDENTITY_DRIFT")
    return holder


def _gate(client):
    runs = client.request("GET", f"/commits/{CANDIDATE_SHA}/check-runs?check_name={GATE_NAME}&filter=latest&per_page=100") or {}
    for run in runs.get("check_runs", []):
        app = run.get("app") or {}
        if (
            str(run.get("head_sha") or "") == CANDIDATE_SHA
            and str(run.get("name") or "") == GATE_NAME
            and str(run.get("status") or "") == "completed"
            and int(app.get("id") or 0) == CHECK_APP_ID
        ):
            return {
                "id": int(run.get("id") or 0),
                "conclusion": str(run.get("conclusion") or ""),
                "summary": str((run.get("output") or {}).get("summary") or ""),
            }
    return None


def should_run(client):
    try:
        return _holder(client) is not None
    except Exception:
        return False


def execute(app):
    client = app.state.github_client
    holder = _holder(client)
    if holder is None:
        raise RuntimeError("STEP5_PROOF_LEASE_NOT_LIVE")
    if client.branch_sha("main") != EXPECTED_MAIN_SHA:
        raise RuntimeError("STEP5_PROOF_MAIN_DRIFT")
    pr = client.request("GET", f"/pulls/{PR_NUMBER}") or {}
    if (
        str((pr.get("head") or {}).get("sha") or "") != CANDIDATE_SHA
        or str((pr.get("base") or {}).get("sha") or "") != EXPECTED_MAIN_SHA
        or pr.get("merged_at")
    ):
        raise RuntimeError("STEP5_PROOF_PR_IDENTITY_DRIFT")
    existing = _gate(client)
    if existing is not None:
        if existing["conclusion"] != "success":
            raise RuntimeError("STEP5_EXISTING_TERMINAL_GATE_FAILED")
        return {
            "status": "GREEN",
            "decision": "STEP5_PROOF_ALREADY_TERMINAL",
            "candidate_sha": CANDIDATE_SHA,
            "check_id": existing["id"],
            "github_actions_fallback": 0,
        }
    request = ProofRequest(
        task_id=TASK_ID,
        workstream=WORKSTREAM,
        candidate_sha=CANDIDATE_SHA,
        lease_id=str(holder["lease_id"]),
        authorization_id=AUTHORIZATION_ID,
        expected_main_sha=EXPECTED_MAIN_SHA,
    )
    result = execute_proof_request(
        request,
        settings=app.state.settings,
        github_client=client,
        orchestrator=app.state.orchestrator,
        receipts=app.state.receipts,
    )
    if str(result.get("status") or "") != "MERGE_AUTHORIZED":
        raise RuntimeError("STEP5_RUNLESS_NOT_MERGE_AUTHORIZED:" + str(result.get("status") or ""))
    gate = _gate(client)
    if gate is None or gate["conclusion"] != "success":
        raise RuntimeError("STEP5_RUNLESS_GATE_READBACK_FAILED")
    return {
        "status": "GREEN",
        "decision": "STEP5_EXACT_HEAD_PROVEN",
        "candidate_sha": CANDIDATE_SHA,
        "lease_id": str(holder["lease_id"]),
        "proof_id": result.get("proof_id"),
        "receipt_digest": result.get("receipt_digest"),
        "failure_class": "NONE",
        "check_id": gate["id"],
        "artifact_count": result.get("artifact_count"),
        "dependency_count": result.get("dependency_count"),
        "static_evidence_count": result.get("static_evidence_count"),
        "public_evidence_count": result.get("public_evidence_count"),
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_visual_cleanup_step5_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if not should_run(app.state.github_client):
            return
        try:
            app.state.cfb_game_total_visual_cleanup_step5_proof = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_visual_cleanup_step5_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_VISUAL_CLEANUP_STEP5_PROOF="
            + json.dumps(app.state.cfb_game_total_visual_cleanup_step5_proof, sort_keys=True),
            flush=True,
        )

    return app
