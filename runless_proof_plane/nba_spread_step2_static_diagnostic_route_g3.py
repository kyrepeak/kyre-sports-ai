from __future__ import annotations

import os

from fastapi import HTTPException
from .nba_spread_step2_static_diagnostic_g3 import execute

ENV = "RPP_NBA_SPREAD_STEP2_DIAGNOSTIC_ON_START"


def install(app):
    @app.get("/diagnostics/nba-spread-step2-g3")
    def diagnostic():
        if os.getenv(ENV, "").strip() != "1":
            raise HTTPException(404, "NBA_SPREAD_STEP2_DIAGNOSTIC_DISABLED")
        return execute(app.state.github_client)
    return app
