from __future__ import annotations

import json
import os
import subprocess

from .workspace import CandidateWorkspace

ENV = "RPP_NBA_SPREAD_STEP2_DIAGNOSTIC_ON_START"
CANDIDATE_SHA = "6804bfe0dff50d37cc8a097eff34a1f6a75526c1"
COMMAND = [
    "python", "-m", "pytest", "-q",
    "tests/test_nba_spread_step2_site_activation_v1.py",
    "tests/test_nba_spread_page_isolation_v1.py",
    "tests/test_devsystem_change_classifier_v1.py",
    "tests/test_cfb_game_total_page2_step8_final_v1.py",
]


def execute(client):
    token = client.auth.installation_token()
    repo_url = f"https://github.com/{client.repository}.git"
    with CandidateWorkspace(repo_url, CANDIDATE_SHA, token=token) as workspace:
        cp = subprocess.run(
            COMMAND,
            cwd=workspace.path,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        return {
            "status": "GREEN" if cp.returncode == 0 else "FAIL",
            "candidate_sha": CANDIDATE_SHA,
            "returncode": int(cp.returncode),
            "stdout": cp.stdout[-10000:],
            "stderr": cp.stderr[-10000:],
            "github_actions_fallback": 0,
            "mutation_authority": False,
        }


def install_startup(app):
    @app.on_event("startup")
    def _run():
        if os.environ.pop(ENV, "").strip() != "1":
            return
        try:
            result = execute(app.state.github_client)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:3000]}
        app.state.nba_spread_step2_static_diagnostic_g3 = result
        print("NBA_SPREAD_STEP2_STATIC_DIAGNOSTIC_G3=" + json.dumps(result, sort_keys=True), flush=True)
    return app
