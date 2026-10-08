from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "api2-finalization-authority-v1-step6-100-percent-finalizer"
WORKSTREAM = "api2-finalization-authority-v1-step6"
CANDIDATE_SHA = "02f1434969b6f468c9300390fe3c6aae50bdd23e"
LEASE_ID = "SCOPE-LEASE-0B3BDBFBD1355D489BE0C914"
AUTHORIZATION_ID = "API2-FINALIZATION-AUTHORITY-V1-STEP6-RUNLESS-GREEN-R2"
EXPECTED_MAIN_SHA = "6c193bab72e6b55e1e39558d3322887643b78a87"


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
    app.state.api2_finalization_authority_step6_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.api2_finalization_authority_step6_proof = execute(app)
        except Exception as exc:
            app.state.api2_finalization_authority_step6_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "API2_FINALIZATION_AUTHORITY_V1_STEP6_RUNLESS="
            + json.dumps(app.state.api2_finalization_authority_step6_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
