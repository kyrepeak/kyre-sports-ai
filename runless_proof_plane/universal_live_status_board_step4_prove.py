from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "universal-live-status-board-v1-step4-enforcement-gate"
WORKSTREAM = "universal-live-status-board-v1"
CANDIDATE_SHA = "3f2281c91332afeb2a8d7d8ac6a3d23792b3f200"
LEASE_ID = "SCOPE-LEASE-31F00A2F706E92B02F98E1A2"
AUTHORIZATION_ID = "AUTH-UNIVERSAL-LIVE-STATUS-BOARD-V1-STEP4-R1"
EXPECTED_MAIN_SHA = "77b6cfb53b5bbb09c88269d366ea0ea075acc91e"


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
    app.state.universal_live_status_board_step4_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.universal_live_status_board_step4_proof = execute(app)
        except Exception as exc:
            app.state.universal_live_status_board_step4_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "UNIVERSAL_LIVE_STATUS_BOARD_STEP4_RUNLESS="
            + json.dumps(app.state.universal_live_status_board_step4_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
