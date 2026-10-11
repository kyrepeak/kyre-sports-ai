from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

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
    original = prior._browser_readback

    def threaded_readback():
        _ensure_chromium()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="cfb-step8-playwright") as pool:
            return pool.submit(original).result(timeout=480)

    prior._browser_readback = threaded_readback
    try:
        return prior.execute(app)
    finally:
        prior._browser_readback = original


def install_startup(app):
    app.state.cfb_step8_terminal_freeze_event_guard_r2 = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:16000]}
        app.state.cfb_step8_terminal_freeze_event_guard_r2 = result
        print("CFB_STEP8_TERMINAL_FREEZE_EVENT_GUARD_R2=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    return app
