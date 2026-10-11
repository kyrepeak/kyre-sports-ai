from __future__ import annotations

import json

from . import cfb_game_total_mobile_production_step8_postmerge_closeout as core
from . import cfb_game_total_mobile_production_step8_postmerge_closeout_v3 as v3

VERIFIED_PREMERGE_CHECK_ID = 114370827167


def execute(app):
    original = core.PREMERGE_CHECK_ID
    try:
        core.PREMERGE_CHECK_ID = VERIFIED_PREMERGE_CHECK_ID
        return v3.execute(app)
    finally:
        core.PREMERGE_CHECK_ID = original


def install_startup(app):
    app.state.cfb_game_total_step8_postmerge_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_step8_postmerge_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_step8_postmerge_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:16000],
            }
        print(
            "CFB_GAME_TOTAL_STEP8_POSTMERGE_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_step8_postmerge_closeout, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
