from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

BRANCH = "cfb-game-total-mobile-production-step8-v1"
EXPECTED_HEAD = "4a5db16fb7aa9628a0dd131c6d394ea41644ba77"
REPO = "https://github.com/kyrepeak/kyre-sports-ai.git"
TEST = "tests/test_cfb_game_total_mobile_production_step8_v1.py"


def execute() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cfb-step8-review-red2-") as tmp:
        root = Path(tmp) / "repo"
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", BRANCH, REPO, str(root)],
            text=True,
            capture_output=True,
            timeout=120,
        )
        if clone.returncode != 0:
            return {"status": "FAIL_INFRA", "detail": (clone.stderr or clone.stdout)[-4000:]}
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if head != EXPECTED_HEAD:
            return {"status": "FAIL_IDENTITY", "expected": EXPECTED_HEAD, "actual": head}
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", TEST],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=240,
        )
        output = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-12000:]
        return {
            "status": "RED_CONFIRMED" if proc.returncode != 0 else "UNEXPECTED_GREEN",
            "head": head,
            "returncode": proc.returncode,
            "detail": output,
        }


def install_startup(app):
    app.state.cfb_step8_review_red2 = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _start():
        def worker():
            try:
                app.state.cfb_step8_review_red2 = execute()
            except Exception as exc:
                app.state.cfb_step8_review_red2 = {"status": "FAIL_INFRA", "error": type(exc).__name__, "detail": str(exc)}
            print("CFB_GAME_TOTAL_STEP8_REVIEW_RED2=" + json.dumps(app.state.cfb_step8_review_red2, sort_keys=True), flush=True)
        threading.Thread(target=worker, daemon=True, name="cfb-step8-review-red2").start()

    return app
