from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

BRANCH = "cfb-game-total-mobile-production-step8-v1"
EXPECTED_HEAD = "2b8e8a1b391fb143aba9cc3cb0828a340bb21894"
TEST = "tests/test_cfb_game_total_mobile_production_step8_v1.py"
REPO = "https://github.com/kyrepeak/kyre-sports-ai.git"


def execute() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cfb-step8-route-red-") as tmp:
        root = Path(tmp) / "repo"
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", BRANCH, REPO, str(root)],
            text=True, capture_output=True, timeout=120,
        )
        if clone.returncode != 0:
            return {"status": "FAIL", "stage": "clone", "detail": (clone.stderr or clone.stdout)[-4000:]}
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if head != EXPECTED_HEAD:
            return {"status": "FAIL", "stage": "identity", "expected_head": EXPECTED_HEAD, "actual_head": head}
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", TEST],
            cwd=root, text=True, capture_output=True, timeout=240,
        )
        output = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-12000:]
        hits = [m for m in ("ks_jump_sport", "authoritative_phoenix_day") if m in output]
        return {
            "status": "RED_CONFIRMED" if proc.returncode != 0 and hits else "FAIL",
            "returncode": proc.returncode,
            "head": head,
            "marker_hits": hits,
            "output_tail": output,
        }


def install_startup(app):
    app.state.cfb_game_total_step8_phoenix_route_red = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_step8_phoenix_route_red = execute()
        except Exception as exc:
            app.state.cfb_game_total_step8_phoenix_route_red = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:5000]
            }
        print(
            "CFB_GAME_TOTAL_STEP8_PHOENIX_ROUTE_RED="
            + json.dumps(app.state.cfb_game_total_step8_phoenix_route_red, sort_keys=True),
            flush=True,
        )

    return app
