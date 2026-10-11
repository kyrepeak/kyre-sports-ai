from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page1-page2-handoff-step7-v1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
CANDIDATE_SHA = "be6a0ddbee8cb85fb9e014a7d6fc1557c25a1a3e"
LEASE_ID = "SCOPE-LEASE-D24C5C7B4F365450B02639CB"
AUTHORIZATION_ID = "AUTH-CFB-GT-PAGE1-PAGE2-HANDOFF-STEP7-R1"
EXPECTED_MAIN_SHA = "0baa35045941adfea5d7a5bafb216efbfed42b7a"


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
    app.state.cfb_game_total_page1_page2_handoff_step7_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page1_page2_handoff_step7_proof = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page1_page2_handoff_step7_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5200],
            }
        print(
            "CFB_GAME_TOTAL_PAGE1_PAGE2_HANDOFF_STEP7_RUNLESS="
            + json.dumps(app.state.cfb_game_total_page1_page2_handoff_step7_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
