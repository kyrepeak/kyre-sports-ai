from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

BRANCH = "cfb-game-total-mobile-production-step8-v1"
EXPECTED_HEAD = "0b8502fad71184feaca1e54884dd11c25f0a4318"
TEST = "tests/test_cfb_game_total_mobile_production_step8_v1.py"
REPO = "https://github.com/kyrepeak/kyre-sports-ai.git"


def execute() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cfb-step8-native-red-") as tmp:
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
            return {"status": "FAIL", "stage": "identity", "expected_head": EXPECTED_HEAD, "actual_head": head}
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", TEST],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=240,
        )
        output = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-12000:]
        markers = ["_find_cfb_frame", "base._find_app_frame(page"]
        hit = [m for m in markers if m in output]
        return {
            "status": "RED_CONFIRMED" if proc.returncode != 0 and hit else "FAIL",
            "returncode": proc.returncode,
            "head": head,
            "marker_hits": hit,
            "output_tail": output,
        }


def install_startup(app):
    app.state.cfb_game_total_step8_native_frame_red = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_step8_native_frame_red = execute()
        except Exception as exc:
            app.state.cfb_game_total_step8_native_frame_red = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5000],
            }
        print(
            "CFB_GAME_TOTAL_STEP8_NATIVE_FRAME_RED="
            + json.dumps(app.state.cfb_game_total_step8_native_frame_red, sort_keys=True),
            flush=True,
        )

    return app
