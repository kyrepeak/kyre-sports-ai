from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page1-v2-step3-matchup-hero-phx"
WORKSTREAM = "cfb-game-total-page1-v2"
CANDIDATE_SHA = "6dc26d7e7afe84905125766c68bbd2065dedb12d"
LEASE_ID = "SCOPE-LEASE-1B99AF86A095301C9EE9FDDB"
AUTHORIZATION_ID = "CFB-GAME-TOTAL-PAGE1-V2-STEP3-RUNLESS-EXACT-HEAD"
EXPECTED_MAIN_SHA = "0244ed0b203ad2996cb6d79409f69ba151029008"


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
    app.state.cfb_game_total_page1_v2_step3_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page1_v2_step3_proof = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page1_v2_step3_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GAME_TOTAL_PAGE1_V2_STEP3_RUNLESS="
            + json.dumps(app.state.cfb_game_total_page1_v2_step3_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
