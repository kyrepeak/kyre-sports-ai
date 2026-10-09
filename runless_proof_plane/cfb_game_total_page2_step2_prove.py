from __future__ import annotations

import json
import re
import subprocess

from .workspace import CandidateWorkspace

CANDIDATE_SHA = "24d4bff2b95bebd9a5335a5b7f38549a5a391474"
EXPECTED_MAIN_SHA = "337e9f2429aee703e821b226cc46ea3b52567986"


def _repo_url(repository: str) -> str:
    return f"https://x-access-token@github.com/{repository}.git"


def _run_pytest(app, sha: str, args: list[str]) -> dict:
    token = app.state.github_auth.installation_token()
    with CandidateWorkspace(
        _repo_url(app.state.settings.repository),
        sha,
        token=token,
    ) as workspace:
        completed = subprocess.run(
            ["python", "-m", "pytest", *args],
            cwd=workspace.path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=900,
            check=False,
        )
    combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
    return {
        "returncode": int(completed.returncode),
        "tail": combined[-12000:],
    }


def execute(app):
    candidate = _run_pytest(app, CANDIDATE_SHA, ["-q", "-x", "--maxfail=1"])
    match = re.search(r"(?:FAILED|ERROR)\s+([^\s]+)", candidate["tail"])
    failing_node = match.group(1) if match else ""
    baseline = None
    if failing_node:
        baseline = _run_pytest(app, EXPECTED_MAIN_SHA, ["-q", failing_node])
    return {
        "status": "DIAGNOSTIC_COMPLETE",
        "candidate_sha": CANDIDATE_SHA,
        "main_sha": EXPECTED_MAIN_SHA,
        "failing_node": failing_node,
        "candidate_returncode": candidate["returncode"],
        "candidate_tail": candidate["tail"],
        "baseline_returncode": None if baseline is None else baseline["returncode"],
        "baseline_tail": "" if baseline is None else baseline["tail"],
    }


def install_startup(app):
    app.state.cfb_game_total_page2_step2_diag = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page2_step2_diag = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_page2_step2_diag = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_PAGE2_STEP2_DIAG="
            + json.dumps(app.state.cfb_game_total_page2_step2_diag, sort_keys=True, default=str),
            flush=True,
        )

    return app
