from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-mobile-production-step8-deploy-refresh-v1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
CANDIDATE_SHA = "b8a693bdce3f0e17a602e67fe89a60f63457b15a"
LEASE_ID = "SCOPE-LEASE-6E91B4C27A53D8F0B21C44E7"
AUTHORIZATION_ID = "AUTH-CFB-GT-STEP8-DEPLOY-REFRESH-R1"
EXPECTED_MAIN_SHA = "1b0169a8a6e644ae6971685fb50b9bd96d510106"


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
    app.state.cfb_step8_deploy_refresh_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_step8_deploy_refresh_proof = execute(app)
        except Exception as exc:
            app.state.cfb_step8_deploy_refresh_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:3000],
            }
        print(
            "CFB_STEP8_DEPLOY_REFRESH_RUNLESS="
            + json.dumps(app.state.cfb_step8_deploy_refresh_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
