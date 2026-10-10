from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "universal-live-status-board-v1-step1-mandatory-status-schema"
WORKSTREAM = "universal-live-status-board-v1"
CANDIDATE_SHA = "7a75423426a92fee5ab98360e9dcea0d578ad971"
LEASE_ID = "SCOPE-LEASE-02767A5C851989556C4788B3"
AUTHORIZATION_ID = "UNIVERSAL-LIVE-STATUS-BOARD-V1-STEP1-RUNLESS-GREEN-R1"
EXPECTED_MAIN_SHA = "3065e960d3363bf6f3d70252c906b9590e7293e9"


def execute(app):
    request = ProofRequest(
        task_id=TASK_ID,
        workstream=WORKSTREAM,
        candidate_sha=CANDIDATE_SHA,
        lease_id=LEASE_ID,
        authorization_id=AUTHORIZATION_ID,
        expected_main_sha=EXPECTED_MAIN_SHA,
    )
    return execute_proof_request(
        request,
        settings=app.state.settings,
        github_client=app.state.github_client,
        orchestrator=app.state.orchestrator,
        receipts=app.state.receipts,
    )


def install_startup(app):
    app.state.universal_live_status_board_step1_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.universal_live_status_board_step1_proof = execute(app)
        except Exception as exc:
            app.state.universal_live_status_board_step1_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "UNIVERSAL_LIVE_STATUS_BOARD_STEP1_RUNLESS="
            + json.dumps(app.state.universal_live_status_board_step1_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
