from __future__ import annotations

import json
import os

from . import nba_spread_step2_postmerge_closeout as core
from . import nba_spread_step2_postmerge_closeout_r2 as r2

ENV = "RPP_NBA_SPREAD_STEP2_POSTMERGE_CLOSEOUT_ON_START"
EXPECTED_REGISTRY_HASH = "fb1bcdefd9efac5ee7b571f1dd47a000c2e17d6ff5bd2dcbc2c8f0c3324e21e3"


def execute(client):
    saved = core.EXPECTED_REGISTRY_HASH
    try:
        core.EXPECTED_REGISTRY_HASH = EXPECTED_REGISTRY_HASH
        result = dict(r2.execute(client))
        result["registry_authority_correction"] = "R3_FRESH_REGISTRY_HASH"
        return result
    finally:
        core.EXPECTED_REGISTRY_HASH = saved


def install_startup(app):
    app.state.nba_spread_step2_postmerge_closeout_r3 = {"status": "NOT_RUN"}

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
        app.state.nba_spread_step2_postmerge_closeout_r3 = result
        print("NBA_SPREAD_STEP2_POSTMERGE_CLOSEOUT_R3=" + json.dumps(result, sort_keys=True), flush=True)

    return app
