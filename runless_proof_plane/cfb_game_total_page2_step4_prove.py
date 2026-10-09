from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page2-step4-outlook-summary"
WORKSTREAM = "cfb-game-total-page2-v1"
CANDIDATE_SHA = "189ff2b13c807f2c5a527b1d6c8f37463e060475"
LEASE_ID = "SCOPE-LEASE-9BB28E7012E82B794572C497"
AUTHORIZATION_ID = "API2-CFB-GAME-TOTAL-PAGE2-STEP4-EXACT-HEAD-R3"
EXPECTED_MAIN_SHA = "c304d28f2dd99f42d1f0bb98930afde8b65e047c"


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
    app.state.cfb_game_total_page2_step4_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page2_step4_proof = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page2_step4_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_PAGE2_STEP4_RUNLESS="
            + json.dumps(app.state.cfb_game_total_page2_step4_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
