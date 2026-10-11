from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

BRANCH = "cfb-game-total-mobile-production-step8-v1"
EXPECTED_HEAD = "f20202d43017f95ca002e6bba408b0d8bfa6d49b"
TEST = "tests/test_cfb_game_total_mobile_production_step8_v1.py"
REPO = "https://github.com/kyrepeak/kyre-sports-ai.git"


def execute() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cfb-step8-red-") as tmp:
        root = Path(tmp) / "repo"
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", BRANCH, REPO, str(root)],
            text=True,
            capture_output=True,
            timeout=120,
        )
        if clone.returncode != 0:
            return {"status": "FAIL", "stage": "clone", "detail": (clone.stderr or clone.stdout)[-3000:]}
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if head != EXPECTED_HEAD:
            return {"status": "FAIL", "stage": "identity", "expected_head": EXPECTED_HEAD, "actual_head": head}
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", TEST],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=180,
        )
        output = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-10000:]
        expected_markers = [
            "Step 8 mobile/production certification owner is not implemented yet",
            "879c28265efde1810a5e30352fa2dcb269c1052a",
            "Step 8 Runless proof plan is not implemented yet",
        ]
        marker_hits = [marker for marker in expected_markers if marker in output]
        return {
            "status": "RED_CONFIRMED" if proc.returncode != 0 and marker_hits else "FAIL",
            "returncode": proc.returncode,
            "head": head,
            "marker_hits": marker_hits,
            "output_tail": output,
        }


def install_startup(app):
    app.state.cfb_game_total_step8_red = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_step8_red = execute()
        except Exception as exc:
            app.state.cfb_game_total_step8_red = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:4000]}
        print("CFB_GAME_TOTAL_STEP8_TDD_RED=" + json.dumps(app.state.cfb_game_total_step8_red, sort_keys=True), flush=True)

    return app
