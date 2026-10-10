from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page2-step7-line-lab-best-bet"
WORKSTREAM = "cfb-game-total-page2-v1"
CANDIDATE_SHA = "a01c3341f2a5d6446e69d5b7da3482d488ed4b6c"
LEASE_ID = "SCOPE-LEASE-FF93328D58902FCDF0143D00"
AUTHORIZATION_ID = "API2-CFB-GAME-TOTAL-PAGE2-STEP7-EXACT-HEAD-R1-RED"
EXPECTED_MAIN_SHA = "bc0ff47ef5771998275456cba454256f6a9ae047"


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
    app.state.cfb_game_total_page2_step7_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page2_step7_proof = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page2_step7_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_PAGE2_STEP7_RUNLESS="
            + json.dumps(app.state.cfb_game_total_page2_step7_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
