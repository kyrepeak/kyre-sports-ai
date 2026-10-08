"""Guarded one-shot launcher for the CFB Step-4 runtime repair.

Inert unless the exact Runless uvicorn service is explicitly armed with
RPP_CFB_STEP4_REPAIR_MODE. The trigger is removed from this process environment
before any proof subprocess starts, preventing recursive/duplicate execution.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import traceback

SERVICE_ID = "srv-db23fee7bikc73ca8ua0"
MODE_ENV = "RPP_CFB_STEP4_REPAIR_MODE"
MERGED_ENV = "RPP_CFB_STEP4_REPAIR_MERGED_SHA"


def _run(mode: str, merged_sha: str) -> None:
    try:
        from runless_proof_plane.config import Settings
        from runless_proof_plane.github_app import GithubAppAuth
        from runless_proof_plane.github_client import GithubClient
        from runless_proof_plane.orchestrator import ProofOrchestrator
        from runless_proof_plane.cfb_step4_runtime_repair import prepare_and_prove, finalize_freeze

        settings = Settings.from_env()
        if settings.bootstrap:
            raise RuntimeError("CFB_STEP4_REPAIR_FULL_RUNLESS_MODE_REQUIRED")
        client = GithubClient(GithubAppAuth(settings), settings.repository)
        if mode == "prepare":
            result = prepare_and_prove(
                client,
                settings=settings,
                orchestrator=ProofOrchestrator(),
                receipts={},
            )
        elif mode == "finalize":
            result = finalize_freeze(client, merged_sha)
        else:
            raise RuntimeError("CFB_STEP4_REPAIR_UNKNOWN_MODE:" + mode)
        print("CFB_STEP4_REPAIR_CONTROL_RESULT=" + json.dumps(result, sort_keys=True, default=str), flush=True)
    except Exception as exc:
        packet = {
            "status": "FAIL",
            "mode": mode,
            "error": type(exc).__name__,
            "detail": str(exc)[:700],
            "traceback": traceback.format_exc(limit=8)[-2600:],
        }
        print("CFB_STEP4_REPAIR_CONTROL_RESULT=" + json.dumps(packet, sort_keys=True), flush=True)


def _is_exact_uvicorn_service() -> bool:
    argv0 = os.path.basename(sys.argv[0] or "").lower()
    return (
        "uvicorn" in argv0
        and os.environ.get("RENDER_SERVICE_ID", "").strip() == SERVICE_ID
    )


if _is_exact_uvicorn_service():
    _mode = os.environ.pop(MODE_ENV, "").strip().lower()
    _merged = os.environ.pop(MERGED_ENV, "").strip().lower()
    if _mode:
        threading.Thread(
            target=_run,
            args=(_mode, _merged),
            daemon=True,
            name="cfb-step4-runtime-repair-control",
        ).start()
