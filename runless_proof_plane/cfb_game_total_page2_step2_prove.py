from __future__ import annotations

import json
import subprocess

from .workspace import CandidateWorkspace

CANDIDATE_SHA = "57001ea06861450ff60b4fed25c4136e906da26f"
EXPECTED_MAIN_SHA = "337e9f2429aee703e821b226cc46ea3b52567986"
REGRESSION_FILES = [
    "tests/test_cfb_game_total_page1_visual_cleanup_step2_top_shell.py",
    "tests/test_cfb_game_total_page1_v2_step3_matchup_hero_phx.py",
    "tests/test_cfb_game_total_page1_visual_cleanup_step5_v191_idempotence.py",
    "tests/test_sitewide_theme_rollout_step4_remaining_pages_v1.py",
]


def _repo_url(repository: str) -> str:
    return f"https://x-access-token@github.com/{repository}.git"


def _run(app, sha: str) -> dict:
    token = app.state.github_auth.installation_token()
    with CandidateWorkspace(_repo_url(app.state.settings.repository), sha, token=token) as workspace:
        completed = subprocess.run(
            ["python", "-m", "pytest", "-q", "-x", "--maxfail=1", *REGRESSION_FILES],
            cwd=workspace.path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600,
            check=False,
        )
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    return {"returncode": int(completed.returncode), "tail": output[-12000:]}


def execute(app):
    candidate = _run(app, CANDIDATE_SHA)
    baseline = _run(app, EXPECTED_MAIN_SHA)
    return {
        "status": "DIAGNOSTIC_COMPLETE",
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": EXPECTED_MAIN_SHA,
        "candidate_returncode": candidate["returncode"],
        "candidate_tail": candidate["tail"],
        "baseline_returncode": baseline["returncode"],
        "baseline_tail": baseline["tail"],
        "regression_files": REGRESSION_FILES,
    }


def install_startup(app):
    app.state.cfb_game_total_page2_step2_regression_diag = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run_startup():
        try:
            app.state.cfb_game_total_page2_step2_regression_diag = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page2_step2_regression_diag = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_PAGE2_STEP2_REGRESSION_DIAG="
            + json.dumps(app.state.cfb_game_total_page2_step2_regression_diag, sort_keys=True, default=str),
            flush=True,
        )

    return app
