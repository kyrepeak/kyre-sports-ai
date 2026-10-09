from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page2-step3-integrated-flow"
WORKSTREAM = "cfb-game-total-page2-v1"
CANDIDATE_SHA = "7fb213598c377ce736539f93256b917d6c2f9f80"
LEASE_ID = "SCOPE-LEASE-113125EEE9134FC49E1F055B"
AUTHORIZATION_ID = "API2-CFB-GAME-TOTAL-PAGE2-STEP3-EXACT-HEAD-R2"
EXPECTED_MAIN_SHA = "b7f54cd695b05674ed7d1947167196bb75d28969"


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
    app.state.cfb_game_total_page2_step3_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page2_step3_proof = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page2_step3_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_PAGE2_STEP3_RUNLESS="
            + json.dumps(app.state.cfb_game_total_page2_step3_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
