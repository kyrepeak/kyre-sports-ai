from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page1-v2-step2-multisource-data-engine"
WORKSTREAM = "cfb-game-total-page1-v2"
CANDIDATE_SHA = "5edb4442881cee3b5e2a37a11406ba39dd88ce29"
LEASE_ID = "SCOPE-LEASE-E23E7BC0C9C91BCF4965E778"
AUTHORIZATION_ID = "CFB-GAME-TOTAL-PAGE1-V2-STEP2-RUNLESS-EXACT-HEAD"
EXPECTED_MAIN_SHA = "8563157c27fe3c13a3084e79230910cdb5e0841a"


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
    app.state.cfb_game_total_page1_v2_step2_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page1_v2_step2_proof = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page1_v2_step2_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GAME_TOTAL_PAGE1_V2_STEP2_RUNLESS="
            + json.dumps(app.state.cfb_game_total_page1_v2_step2_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
