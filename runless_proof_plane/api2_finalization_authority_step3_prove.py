from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "api2-finalization-authority-v1-step3-terminal-completion-latch"
WORKSTREAM = "api2-finalization-authority-v1-step3"
CANDIDATE_SHA = "9658e67e2512b398fda6a7a545b1b2010f0bf184"
LEASE_ID = "SCOPE-LEASE-67048376F53B606480D75ECF"
AUTHORIZATION_ID = "API2-FINALIZATION-AUTHORITY-V1-STEP3-RUNLESS-GREEN-R2"
EXPECTED_MAIN_SHA = "e313222d0c4e55a6217f4aaf62d3afed7aeead13"


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
    app.state.api2_finalization_authority_step3_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.api2_finalization_authority_step3_proof = execute(app)
        except Exception as exc:
            app.state.api2_finalization_authority_step3_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "API2_FINALIZATION_AUTHORITY_V1_STEP3_RUNLESS="
            + json.dumps(app.state.api2_finalization_authority_step3_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
