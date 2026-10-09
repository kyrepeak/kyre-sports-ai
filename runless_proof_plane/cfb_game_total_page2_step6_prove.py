from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page2-step6-trends-scoring-breakdown"
WORKSTREAM = "cfb-game-total-page2-v1"
CANDIDATE_SHA = "6f943656d3be6759c848a338b6a4aef02d968fac"
LEASE_ID = "SCOPE-LEASE-1E81E6BC3D6A9F8C54D20A71"
AUTHORIZATION_ID = "API2-CFB-GAME-TOTAL-PAGE2-STEP6-P1-NONFINITE-RED-R3"
EXPECTED_MAIN_SHA = "be487d7de97d807c7bd02b25a0d206d4d28f94ec"


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
    app.state.cfb_game_total_page2_step6_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page2_step6_proof = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page2_step6_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_PAGE2_STEP6_RUNLESS="
            + json.dumps(app.state.cfb_game_total_page2_step6_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
