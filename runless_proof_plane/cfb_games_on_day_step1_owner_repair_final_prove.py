from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-games-on-day-step1-card-layout-v1"
WORKSTREAM = "cfb-game-total-games-on-day-v1"
CANDIDATE_SHA = "3cec8dd71aeb7337e9eb0c508e564ffafb48bad3"
MAIN_SHA = "60da7cbd5cf05413f2c9d8ce3e8921adb2f58648"
LEASE_ID = "SCOPE-LEASE-AF67B93EB6B292B4553C4F0A"
AUTHORIZATION_ID = "AUTH-CFB-GT-GAMES-ON-DAY-STEP1-OWNER-REPAIR-R1"


class OwnerRepairFinalProofFailure(RuntimeError):
    pass


def _existing_green_gate(client) -> dict | None:
    payload = client.request(
        "GET",
        f"/commits/{CANDIDATE_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    for run in payload.get("check_runs", []):
        if (
            run.get("head_sha") == CANDIDATE_SHA
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
        ):
            return run
    return None


def execute(app):
    client = app.state.github_client
    if client.branch_sha("main") != MAIN_SHA:
        raise OwnerRepairFinalProofFailure("OWNER_REPAIR_FINAL_MAIN_DRIFT")
    commit = client.commit(CANDIDATE_SHA)
    if str(commit.get("sha") or "") != CANDIDATE_SHA:
        raise OwnerRepairFinalProofFailure("OWNER_REPAIR_FINAL_CANDIDATE_DRIFT")

    existing = _existing_green_gate(client)
    if existing:
        return {
            "status": "GREEN",
            "decision": "OWNER_REPAIR_FINAL_ALREADY_MERGE_AUTHORIZED",
            "candidate_sha": CANDIDATE_SHA,
            "main_sha": MAIN_SHA,
            "lease_id": LEASE_ID,
            "check_run_id": existing.get("id"),
            "github_actions_fallback": 0,
        }

    request = ProofRequest(
        task_id=TASK_ID,
        workstream=WORKSTREAM,
        candidate_sha=CANDIDATE_SHA,
        lease_id=LEASE_ID,
        authorization_id=AUTHORIZATION_ID,
        expected_main_sha=MAIN_SHA,
    )
    proof = execute_proof_request(
        request,
        settings=app.state.settings,
        github_client=client,
        orchestrator=app.state.orchestrator,
        receipts=app.state.receipts,
    )
    return {
        "status": "GREEN" if proof.get("status") == "MERGE_AUTHORIZED" else str(proof.get("status") or "UNKNOWN"),
        "decision": "OWNER_REPAIR_FINAL_PREMERGE_PROOF",
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": MAIN_SHA,
        "lease_id": LEASE_ID,
        "proof": proof,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_games_on_day_step1_owner_repair_final_prove = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step1_owner_repair_final_prove = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step1_owner_repair_final_prove = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:2400],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP1_OWNER_REPAIR_FINAL_PROVE="
            + json.dumps(app.state.cfb_games_on_day_step1_owner_repair_final_prove, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
