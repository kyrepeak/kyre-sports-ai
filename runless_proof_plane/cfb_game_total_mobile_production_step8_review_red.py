from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

BRANCH = "cfb-game-total-mobile-production-step8-v1"
EXPECTED_HEAD = "68f4938fe3f5af12c4429a9cbca86900d681eb5d"
REPO = "https://github.com/kyrepeak/kyre-sports-ai.git"
TEST = "tests/test_cfb_game_total_mobile_production_step8_v1.py"


def execute() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cfb-step8-review-red-") as tmp:
        root = Path(tmp) / "repo"
        clone = subprocess.run(["git", "clone", "--depth", "1", "--branch", BRANCH, REPO, str(root)], text=True, capture_output=True, timeout=120)
        if clone.returncode != 0:
            return {"status": "FAIL", "stage": "clone", "detail": (clone.stderr or clone.stdout)[-4000:]}
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if head != EXPECTED_HEAD:
            return {"status": "FAIL", "stage": "identity", "expected_head": EXPECTED_HEAD, "actual_head": head}
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", TEST], cwd=root, text=True, capture_output=True, timeout=240)
        output = ((proc.stdout or "") + "\n" + (proc.stderr or ""))
        if proc.returncode == 0:
            return {"status": "UNEXPECTED_GREEN", "head": head, "detail": output[-9000:]}
        expected_markers = ["current_day_route", "HANDOFF_CERT_DAY", "observed_events", "public_commands"]
        return {"status": "RED_CONFIRMED", "head": head, "marker_hits": [m for m in expected_markers if m in output], "detail": output[-12000:]}


def install_startup(app):
    app.state.cfb_game_total_step8_review_red = {"status": "NOT_RUN"}
    def worker() -> None:
        try:
            app.state.cfb_game_total_step8_review_red = execute()
        except Exception as exc:
            app.state.cfb_game_total_step8_review_red = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:5000]}
        print("CFB_GAME_TOTAL_STEP8_REVIEW_RED=" + json.dumps(app.state.cfb_game_total_step8_review_red, sort_keys=True), flush=True)
    @app.on_event("startup")
    def _start():
        threading.Thread(target=worker, daemon=True, name="cfb-step8-review-red").start()
    return app
