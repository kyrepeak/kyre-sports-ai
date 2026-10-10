from __future__ import annotations

import json
import subprocess
import sys
from threading import Thread

from .cfb_game_total_page2_step8_finalizer import execute


def install_startup(app):
    app.state.cfb_game_total_page2_step8_final = {"status": "NOT_RUN"}

    def _run():
        try:
            install = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                text=True,
                capture_output=True,
                timeout=420,
            )
            if install.returncode != 0:
                detail = (install.stderr or install.stdout or "")[-5000:]
                raise RuntimeError("PAGE2_STEP8_CHROMIUM_INSTALL_FAILED:" + detail)
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:5000]}
        app.state.cfb_game_total_page2_step8_final = result
        print("CFB_GT_PAGE2_STEP8_FINAL=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    @app.on_event("startup")
    def _start_background_finalizer():
        Thread(target=_run, name="cfb-gt-page2-step8-browser-finalizer", daemon=True).start()

    return app
