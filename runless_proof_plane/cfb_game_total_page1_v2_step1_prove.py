from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page1-v2-step1-audit-lock"
WORKSTREAM = "cfb-game-total-page1-v2"
CANDIDATE_SHA = "b54835a412503b4a06a69d84393fe87ac6a65aee"
LEASE_ID = "SCOPE-LEASE-FC714C43D59652FFE1DED04D"
AUTHORIZATION_ID = "CFB-GAME-TOTAL-PAGE1-V2-STEP1-RUNLESS-EXACT-HEAD"
EXPECTED_MAIN_SHA = "371f05b940369c3378ceea8f12fb02e52e5f7f11"


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
    app.state.cfb_game_total_page1_v2_step1_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page1_v2_step1_proof = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page1_v2_step1_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GAME_TOTAL_PAGE1_V2_STEP1_RUNLESS="
            + json.dumps(app.state.cfb_game_total_page1_v2_step1_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
