from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "runless-task17-step1-real-prove"
WORKSTREAM = "runless-task17-step1"
CANDIDATE_SHA = "85e631a923b8433f3a7b86fbd4f0ad4a583a56df"
LEASE_ID = "SCOPE-LEASE-9723EF3FB09AC6A743C304BC"
AUTHORIZATION_ID = "RUNLESS-TASK17-STEP1-AUTH-R3"
EXPECTED_MAIN_SHA = "4036459c8c8cde0ac8f3034b560d7948ad9a5015"


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
    app.state.task17_step1_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step1_proof = execute(app)
        except Exception as exc:
            app.state.task17_step1_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1200],
            }
        print(
            "RUNLESS_TASK17_STEP1_PROOF="
            + json.dumps(app.state.task17_step1_proof, sort_keys=True, default=str),
            flush=True,
        )

    @app.get("/task17-step1-proof/status")
    def _status():
        return app.state.task17_step1_proof

    return app
