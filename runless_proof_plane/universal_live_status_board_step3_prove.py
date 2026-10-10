from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "universal-live-status-board-v1-step3-heartbeat-recovery"
WORKSTREAM = "universal-live-status-board-v1"
CANDIDATE_SHA = "3f95e35187d7f27990f18a41ff40910e8e86928a"
LEASE_ID = "SCOPE-LEASE-C9E38A0EC95B6454261D5E0E"
AUTHORIZATION_ID = "AUTH-UNIVERSAL-LIVE-STATUS-BOARD-V1-STEP3-R1"
EXPECTED_MAIN_SHA = "e80be10496112f6b43f4652a64ddecbfc921b87a"


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
    app.state.universal_live_status_board_step3_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.universal_live_status_board_step3_proof = execute(app)
        except Exception as exc:
            app.state.universal_live_status_board_step3_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "UNIVERSAL_LIVE_STATUS_BOARD_STEP3_RUNLESS="
            + json.dumps(app.state.universal_live_status_board_step3_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
