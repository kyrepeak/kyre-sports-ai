from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

BRANCH = "cfb-game-total-mobile-production-step8-v1"
EXPECTED_HEAD = "0e0e9966e5780711238da92cd1ec412e74c4cd59"
REPO = "https://github.com/kyrepeak/kyre-sports-ai.git"
TEST = "tests/test_cfb_game_total_mobile_production_step8_v1.py"
EVIDENCE_REL = "artifacts/cfb-game-total-step8/cfb_game_total_mobile_production_step8_v1.json"


def _run(cmd: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def execute() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cfb-step8-public-") as tmp:
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

        tests = _run([sys.executable, "-m", "pytest", "-q", TEST], cwd=root, timeout=240)
        if tests.returncode != 0:
            return {"status": "FAIL", "stage": "static-tests", "head": head, "detail": ((tests.stdout or "") + "\n" + (tests.stderr or ""))[-9000:]}

        identity = _run([sys.executable, "devsystem/production_identity_verify_v1.py"], cwd=root, timeout=120)
        if identity.returncode != 0:
            return {"status": "FAIL", "stage": "render-identity", "head": head, "detail": ((identity.stdout or "") + "\n" + (identity.stderr or ""))[-9000:]}

        install = _run([sys.executable, "-m", "playwright", "install", "chromium"], cwd=root, timeout=300)
        if install.returncode != 0:
            return {"status": "FAIL", "stage": "playwright-install", "head": head, "detail": ((install.stdout or "") + "\n" + (install.stderr or ""))[-9000:]}

        public = _run(
            [
                sys.executable,
                "-m",
                "devsystem.cfb_game_total_mobile_production_step8_v1",
                "--base-url",
                "https://pickvault.streamlit.app",
                "--artifact-dir",
                "artifacts/cfb-game-total-step8",
            ],
            cwd=root,
            timeout=900,
        )
        output = ((public.stdout or "") + "\n" + (public.stderr or ""))
        if public.returncode != 0:
            return {"status": "FAIL", "stage": "public-browser", "head": head, "detail": output[-14000:]}

        evidence_path = root / EVIDENCE_REL
        if not evidence_path.is_file():
            return {"status": "FAIL", "stage": "evidence-missing", "head": head, "detail": output[-6000:]}
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        viewports = evidence.get("viewports") or {}
        summary = {
            name: {
                "event_id": ((row.get("page1") or {}).get("exact_event_id")),
                "page1_overflow": ((row.get("page1") or {}).get("horizontal_overflow")),
                "page2_overflow": ((row.get("page2") or {}).get("horizontal_overflow")),
                "page2_visible": ((row.get("page2") or {}).get("all_required_visible")),
            }
            for name, row in viewports.items()
        }
        return {
            "status": "PUBLIC_GREEN",
            "head": head,
            "static_tests": (tests.stdout or "").strip()[-1000:],
            "render_identity_green": "DEVSYSTEM_PRODUCTION_IDENTITY_GREEN" in (identity.stdout or ""),
            "public_marker_green": "CFB_GAME_TOTAL_STEP8_PUBLIC_GREEN" in output,
            "phoenix_date": evidence.get("phoenix_date"),
            "render_commit": (evidence.get("render_identity") or {}).get("certified_commit"),
            "viewports": summary,
        }


def install_startup(app):
    app.state.cfb_game_total_step8_public = {"status": "NOT_RUN"}

    def worker() -> None:
        try:
            app.state.cfb_game_total_step8_public = execute()
        except Exception as exc:
            app.state.cfb_game_total_step8_public = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:5000]}
        print("CFB_GAME_TOTAL_STEP8_PUBLIC_PROOF=" + json.dumps(app.state.cfb_game_total_step8_public, sort_keys=True), flush=True)

    @app.on_event("startup")
    def _start():
        threading.Thread(target=worker, daemon=True, name="cfb-step8-public-proof").start()

    return app
