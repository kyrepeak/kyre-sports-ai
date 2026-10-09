from __future__ import annotations

import json
import subprocess

from .workspace import CandidateWorkspace

CANDIDATE_SHA = "24d4bff2b95bebd9a5335a5b7f38549a5a391474"


def execute(app):
    token = app.state.github_client.auth.installation_token()
    repository = app.state.settings.repository
    url = f"https://x-access-token@github.com/{repository}.git"
    with CandidateWorkspace(url, CANDIDATE_SHA, token=token) as workspace:
        proc = subprocess.run(
            ["python", "-m", "pytest", "-q", "--maxfail=1", "-vv"],
            cwd=workspace.path,
            capture_output=True,
            text=True,
            timeout=900,
        )
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        tail = combined[-12000:]
        return {
            "status": "GREEN" if proc.returncode == 0 else "FAILED",
            "returncode": proc.returncode,
            "candidate_sha": CANDIDATE_SHA,
            "tail": tail,
        }


def install_startup(app):
    app.state.cfb_game_total_page2_step2_diagnostic = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            result = execute(app)
        except Exception as exc:
            result = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:4000],
            }
        app.state.cfb_game_total_page2_step2_diagnostic = result
        print(
            "CFB_GT_PAGE2_STEP2_DIAGNOSTIC="
            + json.dumps(result, sort_keys=True, default=str),
            flush=True,
        )

    return app
