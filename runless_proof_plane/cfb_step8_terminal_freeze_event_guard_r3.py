from __future__ import annotations

import json
import subprocess
import sys
from threading import Thread

from . import cfb_step8_terminal_freeze_event_guard_r1 as prior

MERGED_SHA = "283151c3792a73520a37b54bb8f480910004b6d6"
CANDIDATE_SHA = "1e6e4f51a8dc9a5cf0efca3b893ed4321eb9785a"
ROUTER_FROM = "2a73aba9b5a746a4e5ab8ab7040210df3e705666"
ROUTER_TO = "f6ac3a2a79f8ff1fde6013b399d24d2ffb0ed744"
THAW_ID = "THAW-CFB-GT-STEP8-PAGE1-EVENT-GUARD-R2"
PRE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-page1-event-guard-r2"
FINAL_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-terminal-freeze-event-guard-r3"


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


def _bind_terminal_identity() -> None:
    prior.MERGED_SHA = MERGED_SHA
    prior.CANDIDATE_SHA = CANDIDATE_SHA
    prior.ROUTER_FROM = ROUTER_FROM
    prior.ROUTER_TO = ROUTER_TO
    prior.THAW_ID = THAW_ID
    prior.PRE_OWNER = PRE_OWNER
    prior.FINAL_OWNER = FINAL_OWNER


def execute(app):
    _bind_terminal_identity()
    _ensure_chromium()
    return prior.execute(app)


def install_startup(app):
    app.state.cfb_step8_terminal_freeze_event_guard_r3 = {"status": "STARTING"}

    def _worker():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:16000]}
        app.state.cfb_step8_terminal_freeze_event_guard_r3 = result
        print("CFB_STEP8_TERMINAL_FREEZE_EVENT_GUARD_R3=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    @app.on_event("startup")
    def _run():
        Thread(target=_worker, name="cfb-step8-terminal-finalizer-r3", daemon=True).start()

    return app
