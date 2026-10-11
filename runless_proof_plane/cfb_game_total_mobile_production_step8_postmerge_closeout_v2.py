from __future__ import annotations

from . import cfb_game_total_mobile_production_step8_postmerge_closeout as core
from .registry import GithubRegistryBackend as BaseRegistryBackend


class EagerRegistryBackend(BaseRegistryBackend):
    """Acquire the authoritative registry blob SHA immediately for CAS writes."""

    def __init__(self, client):
        super().__init__(client)
        self.read_registry()


def execute(app):
    original = core.GithubRegistryBackend
    try:
        core.GithubRegistryBackend = EagerRegistryBackend
        return core.execute(app)
    finally:
        core.GithubRegistryBackend = original


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
        import json
        print(
            "CFB_GAME_TOTAL_STEP8_POSTMERGE_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_step8_postmerge_closeout, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
