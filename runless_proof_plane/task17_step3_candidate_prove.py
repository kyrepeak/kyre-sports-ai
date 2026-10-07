from __future__ import annotations

import json

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "runless-task17-step3-post-merge-proof-reuse"
WORKSTREAM = "runless-task17-step3"
CANDIDATE_SHA = "87544f9ddced25a6c390709a4d3c039637a6e4b0"
EXPECTED_MAIN_SHA = "552f7b88b507f132a739900ce05adae96dc7fca1"
LEASE_ID = "SCOPE-LEASE-C20C0E7167152850461F299C"
AUTHORIZATION_ID = "AUTH-RUNLESS-TASK17-STEP3-CANDIDATE-R1"


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
    app.state.task17_step3_candidate_prove = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step3_candidate_prove = execute(app)
        except Exception as exc:
            app.state.task17_step3_candidate_prove = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1600],
            }
        result = app.state.task17_step3_candidate_prove
        receipt = result.get("receipt") or {}
        summary = {
            "status": result.get("status"),
            "state": result.get("state"),
            "candidate_sha": result.get("candidate_sha"),
            "proof_id": result.get("proof_id"),
            "receipt_digest": result.get("receipt_digest") or receipt.get("digest"),
            "proof_fingerprint": result.get("proof_fingerprint"),
            "artifact_count": result.get("artifact_count"),
            "dependency_count": result.get("dependency_count"),
            "static_evidence_count": result.get("static_evidence_count"),
            "public_evidence_count": result.get("public_evidence_count"),
            "inherited_frozen_path_count": result.get("inherited_frozen_path_count"),
            "exact_thawed_path_count": result.get("exact_thawed_path_count"),
            "github_actions_enabled": result.get("github_actions_enabled"),
            "error": result.get("error"),
            "detail": result.get("detail"),
        }
        print(
            "RUNLESS_TASK17_STEP3_CANDIDATE_PROVE=" + json.dumps(summary, sort_keys=True),
            flush=True,
        )

    return app
