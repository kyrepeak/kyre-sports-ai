from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page2-step2-matchup-hero-phx"
WORKSTREAM = "cfb-game-total-page2-v1"
CANDIDATE_SHA = "05590e2d33c01384ec4cd8b92ad728c5829f7b0c"
LEASE_ID = "SCOPE-LEASE-3C34C342A60F9CAD5091D9A2"
AUTHORIZATION_ID = "API2-CFB-GAME-TOTAL-PAGE2-STEP2-RUNLESS-R3"
EXPECTED_MAIN_SHA = "337e9f2429aee703e821b226cc46ea3b52567986"


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
    app.state.cfb_game_total_page2_step2_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page2_step2_proof = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page2_step2_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_PAGE2_STEP2_RUNLESS="
            + json.dumps(app.state.cfb_game_total_page2_step2_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
