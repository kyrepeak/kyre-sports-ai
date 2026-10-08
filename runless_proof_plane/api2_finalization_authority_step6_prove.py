from __future__ import annotations

import contextlib
import io
import json
import os

import pytest

from .models import ProofRequest
from .prove import execute_proof_request
from .workspace import CandidateWorkspace

TASK_ID = "api2-finalization-authority-v1-step6-100-percent-finalizer"
WORKSTREAM = "api2-finalization-authority-v1-step6"
CANDIDATE_SHA = "02f1434969b6f468c9300390fe3c6aae50bdd23e"
LEASE_ID = "SCOPE-LEASE-0B3BDBFBD1355D489BE0C914"
AUTHORIZATION_ID = "API2-FINALIZATION-AUTHORITY-V1-STEP6-RUNLESS-GREEN-R3"
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


def diagnose(app):
    client = app.state.github_client
    token = client.auth.installation_token()
    repository = app.state.settings.repository
    repository_url = f"https://x-access-token@github.com/{repository}.git"
    buffer = io.StringIO()
    original_cwd = os.getcwd()
    with CandidateWorkspace(repository_url, CANDIDATE_SHA, token=token) as workspace:
        try:
            os.chdir(workspace.path)
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                returncode = pytest.main(["-q", "--maxfail=1"])
        finally:
            os.chdir(original_cwd)
    output = buffer.getvalue()
    return {
        "status": "PASS" if int(returncode) == 0 else "FAIL",
        "returncode": int(returncode),
        "candidate_sha": CANDIDATE_SHA,
        "command": "pytest -q --maxfail=1",
        "output_tail": output[-12000:],
    }


def install_startup(app):
    app.state.api2_finalization_authority_step6_diagnostic = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.api2_finalization_authority_step6_diagnostic = diagnose(app)
        except Exception as exc:
            app.state.api2_finalization_authority_step6_diagnostic = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "API2_FINALIZATION_AUTHORITY_V1_STEP6_DIAGNOSTIC="
            + json.dumps(app.state.api2_finalization_authority_step6_diagnostic, sort_keys=True, default=str),
            flush=True,
        )

    return app
