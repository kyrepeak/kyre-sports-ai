from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "api2-finalization-authority-v1-step2-ledger-auto-heal"
WORKSTREAM = "api2-finalization-authority-v1-step2"
CANDIDATE_SHA = "a2346424496c8f4b307c6066028e47fd21b52c68"
LEASE_ID = "SCOPE-LEASE-F76133E0182DB1131C5431A1"
AUTHORIZATION_ID = "API2-FINALIZATION-AUTHORITY-V1-STEP2-RUNLESS-R1"
EXPECTED_MAIN_SHA = "f9908fb83de2e19d3ff1d47b728dac8ba3fef2e0"


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
    app.state.api2_finalization_authority_step2_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.api2_finalization_authority_step2_proof = execute(app)
        except Exception as exc:
            app.state.api2_finalization_authority_step2_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "API2_FINALIZATION_AUTHORITY_V1_STEP2_RUNLESS="
            + json.dumps(app.state.api2_finalization_authority_step2_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
