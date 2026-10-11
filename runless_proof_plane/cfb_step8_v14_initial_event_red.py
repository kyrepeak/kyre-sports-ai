from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

BRANCH = "cfb-game-total-step8-v14-default-query-fix-v1"
EXPECTED_HEAD = "520b4f06246f0273f2a825422eb6ca3658693b26"
REPO = "https://github.com/kyrepeak/kyre-sports-ai.git"
TEST = "tests/test_cfb_game_total_step8_v14_initial_event_v1.py"


def execute() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cfb-step8-v14-red-") as tmp:
        root = Path(tmp) / "repo"
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", BRANCH, REPO, str(root)],
            text=True,
            capture_output=True,
            timeout=120,
        )
        if clone.returncode != 0:
            return {"status": "FAIL", "stage": "clone", "detail": (clone.stderr or clone.stdout)[-4000:]}
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if head != EXPECTED_HEAD:
            return {"status": "FAIL", "stage": "identity", "expected": EXPECTED_HEAD, "actual": head}
        test = subprocess.run([sys.executable, "-m", "pytest", "-q", TEST], cwd=root, text=True, capture_output=True, timeout=120)
        output = ((test.stdout or "") + "\n" + (test.stderr or ""))[-8000:]
        return {
            "status": "RED_CONFIRMED" if test.returncode != 0 else "UNEXPECTED_GREEN",
            "head": head,
            "returncode": test.returncode,
            "output": output,
            "github_actions_fallback": 0,
        }


def install_startup(app):
    app.state.cfb_step8_v14_red = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _start():
        def worker():
            try:
                app.state.cfb_step8_v14_red = execute()
            except Exception as exc:
                app.state.cfb_step8_v14_red = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:5000]}
            print("CFB_STEP8_V14_RED=" + json.dumps(app.state.cfb_step8_v14_red, sort_keys=True), flush=True)
        threading.Thread(target=worker, daemon=True, name="cfb-step8-v14-red").start()

    return app
