from __future__ import annotations

import json
import os

from devsystem.api2_nba_spread_step4_final_freeze_r1 import execute as _execute

ENV_TRIGGER = "RPP_NBA_SPREAD_STEP4_FINALIZE_ON_START"


def install_startup(app):
    @app.on_event("startup")
    def _run():
        if os.environ.pop(ENV_TRIGGER, "").strip() != "1":
            return
        try:
            result = _execute()
        except Exception as exc:
            result = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:2000],
            }
        app.state.nba_spread_step4_finalize = result
        print(
            "NBA_SPREAD_STEP4_FINALIZE="
            + json.dumps(result, sort_keys=True, default=str),
            flush=True,
        )
    return app
