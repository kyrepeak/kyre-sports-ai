from __future__ import annotations

import json
import subprocess

from .workspace import CandidateWorkspace

CANDIDATE_SHA = "babb748fe35e8a97a3a49f39ed3f67f9e126f269"
TEST = "tests/test_cfb_game_total_games_on_day_step4_interaction_mobile_v1.py"


def execute(app):
    client = app.state.github_client
    if client.branch_sha("cfb-game-total-games-on-day-step4-interaction-mobile-v1") != CANDIDATE_SHA:
        return {"status": "FAIL", "detail": "CANDIDATE_DRIFT"}
    token = client.auth.installation_token()
    repo_url = f"https://x-access-token@github.com/{client.repository}.git"
    with CandidateWorkspace(repo_url, CANDIDATE_SHA, token=token) as workspace:
        result = subprocess.run(
            ["python", "-m", "pytest", "-q", TEST],
            cwd=workspace.path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
            check=False,
        )
    output = result.stdout[-5000:]
    expected = "Step-4 interaction owner is not implemented yet" in output
    return {
        "status": "RED_CONFIRMED" if result.returncode != 0 and expected else "FAIL",
        "returncode": result.returncode,
        "expected_failure": expected,
        "candidate_sha": CANDIDATE_SHA,
        "output_tail": output,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_games_on_day_step4_red = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step4_red = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step4_red = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:3200]
            }
        print("CFB_GAMES_ON_DAY_STEP4_RED=" + json.dumps(app.state.cfb_games_on_day_step4_red, sort_keys=True), flush=True)

    return app
