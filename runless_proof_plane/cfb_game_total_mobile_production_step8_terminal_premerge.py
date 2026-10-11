from __future__ import annotations

import json

from . import cfb_game_total_mobile_production_step8_premerge as premerge
from . import cfb_game_total_mobile_production_step8_scope as scope


def execute(app):
    authority = scope.execute(app)
    if authority.get("status") != "GREEN":
        raise RuntimeError("STEP8_SCOPE_NOT_GREEN")
    proof = premerge.execute(app)
    return {
        "status": proof.get("status"),
        "decision": "STEP8_TERMINAL_PREMERGE",
        "candidate_sha": premerge.CANDIDATE_SHA,
        "authority": authority,
        "premerge": proof,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_step8_terminal_premerge = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_step8_terminal_premerge = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_step8_terminal_premerge = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5000],
            }
        print(
            "CFB_GAME_TOTAL_STEP8_TERMINAL_PREMERGE="
            + json.dumps(app.state.cfb_game_total_step8_terminal_premerge, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
