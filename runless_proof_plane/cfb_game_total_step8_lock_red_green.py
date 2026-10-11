from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

BRANCH = "cfb-game-total-mobile-production-step8-v1"
RED_HEAD = "9110ac62ff8a879b80cfe2060d03a73869df4aa5"
GREEN_HEAD = "a1fbecbb5d5dd96d71ad21d4961bf8407c80be9e"
REPO = "https://github.com/kyrepeak/kyre-sports-ai.git"
TEST = "tests/test_cfb_game_total_page1_default_selection_step8_v1.py"


def _pytest(root: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", TEST],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return proc.returncode, ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-12000:]


def execute() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cfb-step8-lock-rg-") as tmp:
        root = Path(tmp) / "repo"
        clone = subprocess.run(
            ["git", "clone", "--depth", "3", "--branch", BRANCH, REPO, str(root)],
            text=True,
            capture_output=True,
            timeout=120,
        )
        if clone.returncode != 0:
            return {"status": "FAIL_INFRA", "detail": (clone.stderr or clone.stdout)[-4000:]}
        current = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if current != GREEN_HEAD:
            return {"status": "FAIL_IDENTITY", "expected_green_head": GREEN_HEAD, "actual": current}

        subprocess.run(["git", "checkout", "--detach", RED_HEAD], cwd=root, check=True, text=True, capture_output=True)
        red_rc, red_output = _pytest(root)
        if red_rc == 0:
            return {"status": "UNEXPECTED_RED_GREEN", "red_head": RED_HEAD, "detail": red_output}

        subprocess.run(["git", "checkout", "--detach", GREEN_HEAD], cwd=root, check=True, text=True, capture_output=True)
        green_rc, green_output = _pytest(root)
        if green_rc != 0:
            return {
                "status": "GREEN_REPAIR_FAILED",
                "red_head": RED_HEAD,
                "green_head": GREEN_HEAD,
                "red_detail": red_output,
                "green_detail": green_output,
            }
        return {
            "status": "RED_GREEN_CONFIRMED",
            "red_head": RED_HEAD,
            "green_head": GREEN_HEAD,
            "red_detail": red_output,
            "green_detail": green_output,
        }


def install_startup(app):
    app.state.cfb_step8_lock_red_green = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _start():
        def worker():
            try:
                app.state.cfb_step8_lock_red_green = execute()
            except Exception as exc:
                app.state.cfb_step8_lock_red_green = {"status": "FAIL_INFRA", "error": type(exc).__name__, "detail": str(exc)}
            print("CFB_GAME_TOTAL_STEP8_LOCK_RED_GREEN=" + json.dumps(app.state.cfb_step8_lock_red_green, sort_keys=True), flush=True)
        threading.Thread(target=worker, daemon=True, name="cfb-step8-lock-rg").start()

    return app
