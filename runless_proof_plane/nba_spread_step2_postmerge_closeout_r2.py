from __future__ import annotations

import json
import os

from . import nba_spread_step2_postmerge_closeout as core

ENV = "RPP_NBA_SPREAD_STEP2_POSTMERGE_CLOSEOUT_ON_START"
MAIN_SHA = "30e803ea943091d07e760d9d4e003e110cbc29ed"
RECEIPT_DIGEST = "bf1f123a63a6043321de5f85e221d0061aa37f99c8eef0fea25126145cd247ef"
CHECK_RUN_ID = 114641075795


def execute(client):
    saved = {
        "MAIN_SHA": core.MAIN_SHA,
        "RECEIPT_DIGEST": core.RECEIPT_DIGEST,
        "CHECK_RUN_ID": core.CHECK_RUN_ID,
    }
    try:
        core.MAIN_SHA = MAIN_SHA
        core.RECEIPT_DIGEST = RECEIPT_DIGEST
        core.CHECK_RUN_ID = CHECK_RUN_ID
        result = dict(core.execute(client))
        result["authority_metadata_correction"] = "R2_FRESH_GITHUB_TRUTH"
        return result
    finally:
        for name, value in saved.items():
            setattr(core, name, value)


def install_startup(app):
    app.state.nba_spread_step2_postmerge_closeout_r2 = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if os.environ.pop(ENV, "").strip() != "1":
            return
        try:
            result = execute(app.state.github_client)
        except Exception as exc:
            result = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        app.state.nba_spread_step2_postmerge_closeout_r2 = result
        print("NBA_SPREAD_STEP2_POSTMERGE_CLOSEOUT_R2=" + json.dumps(result, sort_keys=True), flush=True)

    return app
