from __future__ import annotations

import json
import subprocess

from .workspace import CandidateWorkspace

CANDIDATE_SHA = "701c4f098e894191090e6604b8a4d133d3d2097e"


def execute(app):
    client = app.state.github_client
    token = client.auth.installation_token()
    repository = getattr(client, "repository", app.state.settings.repository)
    repo_url = f"https://x-access-token@github.com/{repository}.git"
    with CandidateWorkspace(repo_url, CANDIDATE_SHA, token=token) as workspace:
        cp = subprocess.run(
            ["python", "-m", "pytest", "-q", "--maxfail=25"],
            cwd=workspace.path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=1800,
            check=False,
        )
    lines = cp.stdout.splitlines()
    failed = [line.strip() for line in lines if line.startswith("FAILED ")]
    errors = [line.strip() for line in lines if line.startswith("ERROR ")]
    summary = [line.strip() for line in lines[-80:] if (" failed" in line or " passed" in line or " error" in line)]
    return {
        "status": "DIAGNOSTIC_COMPLETE",
        "candidate_sha": CANDIDATE_SHA,
        "returncode": cp.returncode,
        "failed": failed[:50],
        "errors": errors[:50],
        "summary": summary[-20:],
        "tail": "\n".join(lines[-120:])[-12000:],
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_games_on_day_step3_diagnostic = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step3_diagnostic = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step3_diagnostic = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5000],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP3_DIAGNOSTIC="
            + json.dumps(app.state.cfb_games_on_day_step3_diagnostic, sort_keys=True),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
