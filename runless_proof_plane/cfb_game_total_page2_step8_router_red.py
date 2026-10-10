from __future__ import annotations

import json
import subprocess
from threading import Thread

from .workspace import CandidateWorkspace

CANDIDATE_SHA = "4e292b2f1dd325e17cca63505a26f225fe4b9905"
TEST = "tests/test_cfb_game_total_page2_step8_final_v1.py"
TEST_NAME = "test_step8_router_restores_query_route_before_selected_event_activation"


def execute(app) -> dict:
    client = app.state.github_client
    settings = app.state.settings
    token = client.auth.installation_token()
    repository_url = f"https://x-access-token@github.com/{settings.repository}.git"
    with CandidateWorkspace(repository_url, CANDIDATE_SHA, token=token) as workspace:
        completed = subprocess.run(
            ["python", "-m", "pytest", "-q", TEST, "-k", TEST_NAME],
            cwd=workspace.path,
            text=True,
            capture_output=True,
            timeout=180,
        )
    output = ((completed.stdout or "") + "\n" + (completed.stderr or ""))[-6000:]
    if completed.returncode == 0:
        raise RuntimeError("STEP8_ROUTER_RED_UNEXPECTED_PASS")
    if TEST_NAME not in output or "AssertionError" not in output:
        raise RuntimeError("STEP8_ROUTER_RED_WRONG_FAILURE:" + output)
    return {
        "status": "RED_EXPECTED",
        "candidate_sha": CANDIDATE_SHA,
        "test": TEST_NAME,
        "returncode": completed.returncode,
        "detail": output[-2500:],
    }


def install_startup(app):
    app.state.cfb_game_total_page2_step8_router_red = {"status": "NOT_RUN"}

    def _run():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:6000]}
        app.state.cfb_game_total_page2_step8_router_red = result
        print("CFB_GT_PAGE2_STEP8_ROUTER_RED=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    @app.on_event("startup")
    def _start():
        Thread(target=_run, name="cfb-gt-page2-step8-router-red", daemon=True).start()

    return app
