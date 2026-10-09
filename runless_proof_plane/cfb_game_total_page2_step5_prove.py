from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page2-step5-team-snapshot-key-drivers"
WORKSTREAM = "cfb-game-total-page2-v1"
CANDIDATE_SHA = "0fc9376a2ef9c4a569e1838daabf4e1d367dbcb6"
LEASE_ID = "SCOPE-LEASE-10324E9533725D1757F3BF30"
AUTHORIZATION_ID = "API2-CFB-GAME-TOTAL-PAGE2-STEP5-EXACT-HEAD-R1-RED"
EXPECTED_MAIN_SHA = "2717651c5b8a5fb08ef4bbc5d7402fa5d6c3fc1f"


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
    app.state.cfb_game_total_page2_step5_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page2_step5_proof = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page2_step5_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_PAGE2_STEP5_RUNLESS="
            + json.dumps(app.state.cfb_game_total_page2_step5_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
