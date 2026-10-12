from __future__ import annotations

import json
import os

from .nba_spread_step3_authority_finalize import finalize_from_env

ENV_TRIGGER = "RPP_NBA_SPREAD_STEP3_FINALIZE_ON_START"


def install_startup(app):
    @app.on_event("startup")
    def _run():
        if os.environ.pop(ENV_TRIGGER, "").strip() != "1":
            return
        try:
            result = finalize_from_env(app.state.github_client)
        except Exception as exc:
            result = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:2000],
            }
        app.state.nba_spread_step3_finalize = result
        print(
            "NBA_SPREAD_STEP3_FINALIZE="
            + json.dumps(result, sort_keys=True, default=str),
            flush=True,
        )
    return app
