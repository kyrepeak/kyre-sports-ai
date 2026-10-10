from __future__ import annotations

import json
import subprocess
import sys

from . import cfb_games_on_day_step1_closeout as core


class CfbGamesOnDayStep1CloseoutV2Failure(RuntimeError):
    pass


def _public_mobile_proof_subprocess() -> dict:
    """Run the synchronous Playwright proof outside Uvicorn's asyncio loop."""
    script = (
        "import json; "
        "from runless_proof_plane import cfb_games_on_day_step1_closeout as core; "
        "result = core._public_mobile_proof(); "
        "print('CFB_GAMES_ON_DAY_STEP1_PUBLIC_PROOF=' + json.dumps(result, sort_keys=True))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=520,
        check=False,
    )
    marker = "CFB_GAMES_ON_DAY_STEP1_PUBLIC_PROOF="
    payload_line = next(
        (line[len(marker):] for line in reversed(completed.stdout.splitlines()) if line.startswith(marker)),
        "",
    )
    if completed.returncode != 0 or not payload_line:
        raise CfbGamesOnDayStep1CloseoutV2Failure(
            "PUBLIC_PROOF_SUBPROCESS_FAILED:"
            + (completed.stdout[-2400:] if completed.stdout else f"rc={completed.returncode}")
        )
    try:
        payload = json.loads(payload_line)
    except json.JSONDecodeError as exc:
        raise CfbGamesOnDayStep1CloseoutV2Failure("PUBLIC_PROOF_JSON_INVALID") from exc
    if payload.get("status") != "GREEN":
        raise CfbGamesOnDayStep1CloseoutV2Failure("PUBLIC_PROOF_NOT_GREEN")
    return payload


def execute(app):
    original = core._public_mobile_proof
    core._public_mobile_proof = _public_mobile_proof_subprocess
    try:
        return core.execute(app)
    finally:
        core._public_mobile_proof = original


def install_startup(app):
    app.state.cfb_games_on_day_step1_closeout_v2 = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step1_closeout_v2 = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step1_closeout_v2 = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:2400],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP1_CLOSEOUT_V2="
            + json.dumps(app.state.cfb_games_on_day_step1_closeout_v2, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
