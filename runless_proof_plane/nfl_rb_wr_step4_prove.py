from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time

from devsystem.runless_proof_plan_v1 import validate_command

from . import executor as runless_executor
from .models import FailureClass, ProofRequest, SliceEvidence
from .prove import execute_proof_request

TASK_ID = "nfl-rb-wr-render-repair-step4-mobile-route"
WORKSTREAM = "nfl-rb-wr-render-repair-v1"
CANDIDATE_SHA = "2ce1446a7d260e9db27b24469bd8b34ad70f23ae"
LEASE_ID = "SCOPE-LEASE-NFL-RB-WR-STEP4-219"
AUTHORIZATION_ID = "NFL-RB-WR-STEP4-CARD-DOM-2CE1446A"
EXPECTED_MAIN_SHA = "7854d5772333482947f9f2d4bda71cf73ded72b5"
ENV_FLAG = "RPP_NFL_RB_WR_STEP4_SUBMIT_ON_START"


def should_run() -> bool:
    return os.getenv(ENV_FLAG, "").strip() == "1"


def _digest(text: str) -> str:
    return hashlib.sha256(str(text or "").encode()).hexdigest()


def _tail(value: object, limit: int = 6000) -> str:
    if isinstance(value, bytes):
        text = value.decode(errors="replace")
    else:
        text = str(value or "")
    return text[-limit:]


def _diagnostic_execute_command(command, cwd, timeout_seconds: int):
    cmd = list(validate_command(tuple(command)))
    start = time.monotonic()
    try:
        cp = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        ok = cp.returncode == 0
        if not ok:
            print(
                "NFL_RB_WR_STEP4_COMMAND_FAILURE="
                + json.dumps(
                    {
                        "command": " ".join(cmd),
                        "returncode": cp.returncode,
                        "stdout_tail": _tail(cp.stdout),
                        "stderr_tail": _tail(cp.stderr),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        return SliceEvidence(
            name=" ".join(cmd),
            ok=ok,
            command=cmd,
            stdout_digest=_digest(cp.stdout),
            stderr_digest=_digest(cp.stderr),
            duration_seconds=time.monotonic() - start,
            failure_class=FailureClass.NONE if ok else FailureClass.STATIC_PROOF,
        )
    except subprocess.TimeoutExpired as exc:
        print(
            "NFL_RB_WR_STEP4_COMMAND_TIMEOUT="
            + json.dumps(
                {
                    "command": " ".join(cmd),
                    "timeout_seconds": timeout_seconds,
                    "stdout_tail": _tail(exc.stdout),
                    "stderr_tail": _tail(exc.stderr),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return SliceEvidence(
            name=" ".join(cmd),
            ok=False,
            command=cmd,
            stdout_digest=_digest(_tail(exc.stdout, 100000)),
            stderr_digest=_digest(_tail(exc.stderr, 100000)),
            duration_seconds=time.monotonic() - start,
            failure_class=FailureClass.INFRA,
        )


def _install_diagnostic_executor() -> None:
    runless_executor.execute_command = _diagnostic_execute_command


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
    _install_diagnostic_executor()
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
