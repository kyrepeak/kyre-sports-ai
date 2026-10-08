from __future__ import annotations

import json
import os
import subprocess
import sys

from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "nfl-rb-wr-render-repair-step4-mobile-route"
WORKSTREAM = "nfl-rb-wr-render-repair-v1"
CANDIDATE_SHA = "77a65d770f2d09d8bcf357aa5c35d24397924496"
LEASE_ID = "SCOPE-LEASE-NFL-RB-WR-STEP4-219"
AUTHORIZATION_ID = "NFL-RB-WR-STEP4-R3B-77A65D77"
EXPECTED_MAIN_SHA = "7854d5772333482947f9f2d4bda71cf73ded72b5"
ENV_FLAG = "RPP_NFL_RB_WR_STEP4_SUBMIT_ON_START"


def should_run() -> bool:
    return os.getenv(ENV_FLAG, "").strip() == "1"


def _ensure_chromium() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=240,
        check=False,
    )
    if proc.returncode != 0:
        tail = " ".join((proc.stdout or "").split())[-1200:]
        raise RuntimeError("RUNLESS_PLAYWRIGHT_CHROMIUM_INSTALL_FAILED:" + tail)


def execute(app):
    _ensure_chromium()
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
    app.state.nfl_rb_wr_step4_proof = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if not should_run():
            return
        try:
            app.state.nfl_rb_wr_step4_proof = execute(app)
        except Exception as exc:
            app.state.nfl_rb_wr_step4_proof = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "NFL_RB_WR_STEP4_RUNLESS="
            + json.dumps(app.state.nfl_rb_wr_step4_proof, sort_keys=True, default=str),
            flush=True,
        )

    return app
