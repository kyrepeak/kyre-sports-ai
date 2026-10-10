from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page2-step7-line-lab-best-bet"
WORKSTREAM = "cfb-game-total-page2-v1"
CANDIDATE_SHA = "5bbe40b203f1e7879cae631cb199a744b97fcf69"
LEASE_ID = "SCOPE-LEASE-8551AF7C8DAD5563D85C4F75"
AUTHORIZATION_ID = "API2-CFB-GAME-TOTAL-PAGE2-STEP7-REVIEW-RED-R4"
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
