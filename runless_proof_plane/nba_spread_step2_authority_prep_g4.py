from __future__ import annotations

import json
import os

from . import nba_spread_step2_authority_prep_g3 as core

ENV = "RPP_NBA_SPREAD_STEP2_AUTHORITY_PREP_ON_START"
CANDIDATE_SHA = "bfae122c36ea29d18a64a9e7ff4c40b06e24640f"
PRIOR_CANDIDATE_SHA = "6804bfe0dff50d37cc8a097eff34a1f6a75526c1"


def execute(client):
    saved_candidate = core.CANDIDATE_SHA
    saved_prior = core.PRIOR_CANDIDATE_SHA
    try:
        core.CANDIDATE_SHA = CANDIDATE_SHA
        core.PRIOR_CANDIDATE_SHA = PRIOR_CANDIDATE_SHA
        result = dict(core.execute(client))
        result["authority_generation"] = 4
        return result
    finally:
        core.CANDIDATE_SHA = saved_candidate
        core.PRIOR_CANDIDATE_SHA = saved_prior


def install_startup(app):
    @app.on_event("startup")
    def _run():
        if os.environ.pop(ENV, "").strip() != "1":
            return
        try:
            result = execute(app.state.github_client)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:1800]}
        app.state.nba_spread_step2_authority_prep_g4 = result
        print("NBA_SPREAD_STEP2_AUTHORITY_PREP_G4=" + json.dumps(result, sort_keys=True), flush=True)
    return app
