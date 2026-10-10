from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

CANDIDATE_SHA = "5ba37d28f04b85d3589899d2e3f4c47b8976b985"
TEST_PATH = "tests/test_cfb_game_total_games_on_day_step3_details_v1.py"
EXPECTED = "Step-3 details owner is not implemented yet"


def execute(app):
    client = app.state.github_client
    raw = client.content(TEST_PATH, ref=CANDIDATE_SHA)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("STEP3_RED_TEST_READ_FAILED")
    text = base64.b64decode(raw["content"]).decode("utf-8")
    with tempfile.TemporaryDirectory(prefix="cfb-step3-red-") as temp:
        root = Path(temp)
        path = root / TEST_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", str(path), "-k", "additive_owner_exists"],
            cwd=str(root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
            check=False,
        )
    output = completed.stdout[-4000:]
    if completed.returncode == 0:
        raise RuntimeError("STEP3_RED_UNEXPECTED_PASS")
    if EXPECTED not in output:
        raise RuntimeError("STEP3_RED_WRONG_FAILURE:" + output[-1800:])
    return {
        "status": "EXPECTED_RED",
        "candidate_sha": CANDIDATE_SHA,
        "test": TEST_PATH,
        "returncode": completed.returncode,
        "expected_failure": EXPECTED,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_games_on_day_step3_red = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step3_red = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step3_red = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:3200],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP3_RED="
            + json.dumps(app.state.cfb_games_on_day_step3_red, sort_keys=True),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
