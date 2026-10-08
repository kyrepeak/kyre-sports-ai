from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "api2-finalization-authority-v1-step5-authority-garbage-collector"
WORKSTREAM = "api2-finalization-authority-v1-step5"
CANDIDATE_SHA = "2dc37818dce15a606168a4cb74c6e322d4a2d630"
LEASE_ID = "SCOPE-LEASE-CBE69BC6B4D5EE8B05BB2E7F"
AUTHORIZATION_ID = "API2-FINALIZATION-AUTHORITY-V1-STEP5-RUNLESS-GREEN-R1"
EXPECTED_MAIN_SHA = "b42b320e69d4894ed2ec5bbd3a065824d35d6fff"


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
    app.state.api2_finalization_authority_step5_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.api2_finalization_authority_step5_proof = execute(app)
        except Exception as exc:
            app.state.api2_finalization_authority_step5_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "API2_FINALIZATION_AUTHORITY_V1_STEP5_RUNLESS="
            + json.dumps(app.state.api2_finalization_authority_step5_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
