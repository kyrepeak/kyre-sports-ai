from __future__ import annotations

import json
import subprocess
import sys
from threading import Thread

from . import cfb_step8_terminal_freeze_event_guard_r1 as prior


def _ensure_chromium() -> None:
    install = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        text=True,
        capture_output=True,
        timeout=360,
        check=False,
    )
    if install.returncode != 0:
        detail = ((install.stdout or "") + "\n" + (install.stderr or ""))[-12000:]
        raise RuntimeError("STEP8_CHROMIUM_INSTALL_FAILED:" + detail)


def execute(app):
    # This function is intentionally called from a dedicated background thread.
    # That keeps Playwright Sync API and the browser install completely outside
    # FastAPI/uvicorn's asyncio startup loop while allowing the web service to
    # bind its port immediately.
    _ensure_chromium()
    return prior.execute(app)


def install_startup(app):
    app.state.cfb_step8_terminal_freeze_event_guard_r2 = {"status": "STARTING"}

    def _worker():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:16000]}
        app.state.cfb_step8_terminal_freeze_event_guard_r2 = result
        print("CFB_STEP8_TERMINAL_FREEZE_EVENT_GUARD_R2=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    @app.on_event("startup")
    def _run():
        Thread(target=_worker, name="cfb-step8-terminal-finalizer", daemon=True).start()

    return app
