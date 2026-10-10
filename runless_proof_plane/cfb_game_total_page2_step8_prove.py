from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page2-step8-final-responsive-live-data"
WORKSTREAM = "cfb-game-total-page2-v1"
CANDIDATE_SHA = "2743ec3197d881279260d2ab407d0bb2f49d2ed2"
LEASE_ID = "SCOPE-LEASE-49C270AAD437F764D45964F1"
AUTHORIZATION_ID = "API2-CFB-GAME-TOTAL-PAGE2-STEP8-EXACT-HEAD-GREEN-R1"
EXPECTED_MAIN_SHA = "c7bb9383c510c79dcca88f5e33d533a18085ee40"


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
    app.state.cfb_game_total_page2_step8_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page2_step8_proof = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page2_step8_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_PAGE2_STEP8_RUNLESS="
            + json.dumps(app.state.cfb_game_total_page2_step8_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
