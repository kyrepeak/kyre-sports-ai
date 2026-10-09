from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page1-visual-cleanup-step1-target-lock"
WORKSTREAM = "cfb-game-total-page1-visual-cleanup-v1"
CANDIDATE_SHA = "3236f455437e8e2a83eaa669d1d9d913b408bae2"
LEASE_ID = "SCOPE-LEASE-CFB-GT-P1-VISUAL-CLEANUP-STEP1-240"
AUTHORIZATION_ID = "CFB-GT-P1-VISUAL-CLEANUP-STEP1-RED-R1"
EXPECTED_MAIN_SHA = "1eb550e58964ace5f9551a484d1c65cd49f8fc20"


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
    app.state.cfb_game_total_visual_cleanup_step1 = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_visual_cleanup_step1 = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_visual_cleanup_step1 = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_VISUAL_CLEANUP_STEP1_RUNLESS="
            + json.dumps(app.state.cfb_game_total_visual_cleanup_step1, sort_keys=True, default=str),
            flush=True,
        )

    return app
