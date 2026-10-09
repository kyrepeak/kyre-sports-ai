from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state
from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page1-visual-cleanup-step3-overview-team-snapshot"
WORKSTREAM = "cfb-game-total-page1-visual-cleanup-v1"
CANDIDATE_SHA = "188b065e404141373c3f1157b7729243ef948e16"
EXPECTED_MAIN_SHA = "036dbb2ab3a0e24ce3e1cb16c1b2f9469cfce2f4"
PR_NUMBER = 1481
LEASE_OWNER = "api2-cfb-game-total-page1-visual-cleanup-step3-convergence"
AUTHORIZATION_ID = "AUTH-CFB-GT-P1-VISUAL-CLEANUP-STEP3-1481"
GATE_NAME = "runless-final-gate"
CHECK_APP_ID = 5204253

LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"


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
        _decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "CFB_GT_STEP3_PROOF_LEASE")
    )
    now = datetime.now(timezone.utc)
    matches = [
        item for item in state.get("holders", [])
        if item.get("owner_id") == LEASE_OWNER
        and now < _utc(item["expires_at_utc"])
    ]
    if len(matches) != 1:
        return None
    holder = matches[0]
    identity = (holder.get("scope") or {}).get("resource_identity") or {}
    if (
        str(identity.get("candidate_sha") or "") != CANDIDATE_SHA
        or str(identity.get("main_sha") or "") != EXPECTED_MAIN_SHA
        or str(identity.get("workstream") or "") != WORKSTREAM
        or str(identity.get("pr_number") or "") != str(PR_NUMBER)
    ):
        raise RuntimeError("CFB_GT_STEP3_PROOF_LEASE_IDENTITY_DRIFT")
    return holder


def _terminal_gate(client) -> dict | None:
    runs = client.request(
        "GET",
        f"/commits/{CANDIDATE_SHA}/check-runs?check_name={GATE_NAME}&filter=latest&per_page=100",
    ) or {}
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


def should_run(client) -> bool:
    try:
        return _live_lease(client) is not None
    except Exception:
        return False


def execute(app) -> dict:
    client = app.state.github_client
    holder = _live_lease(client)
    if holder is None:
        raise RuntimeError("CFB_GT_STEP3_PROOF_LEASE_NOT_LIVE")
    if client.branch_sha("main") != EXPECTED_MAIN_SHA:
        raise RuntimeError("CFB_GT_STEP3_PROOF_MAIN_DRIFT")
    pr = client.request("GET", f"/pulls/{PR_NUMBER}") or {}
    if (
        str((pr.get("head") or {}).get("sha") or "") != CANDIDATE_SHA
        or str((pr.get("base") or {}).get("sha") or "") != EXPECTED_MAIN_SHA
        or pr.get("merged_at")
    ):
        raise RuntimeError("CFB_GT_STEP3_PROOF_PR_IDENTITY_DRIFT")

    existing = _terminal_gate(client)
    if existing is not None:
        if existing["conclusion"] != "success":
            raise RuntimeError("CFB_GT_STEP3_EXISTING_TERMINAL_GATE_FAILED")
        return {
            "status": "GREEN",
            "decision": "CFB_GT_STEP3_PROOF_ALREADY_TERMINAL",
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
        raise RuntimeError("CFB_GT_STEP3_RUNLESS_NOT_MERGE_AUTHORIZED:" + str(result.get("status") or ""))
    gate = _terminal_gate(client)
    if gate is None or gate["conclusion"] != "success":
        raise RuntimeError("CFB_GT_STEP3_RUNLESS_GATE_READBACK_FAILED")
    return {
        "status": "GREEN",
        "decision": "CFB_GT_STEP3_EXACT_HEAD_PROVEN",
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
    app.state.cfb_game_total_visual_cleanup_step3_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if not should_run(app.state.github_client):
            return
        try:
            app.state.cfb_game_total_visual_cleanup_step3_proof = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_visual_cleanup_step3_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_VISUAL_CLEANUP_STEP3_PROOF="
            + json.dumps(app.state.cfb_game_total_visual_cleanup_step3_proof, sort_keys=True),
            flush=True,
        )

    return app
