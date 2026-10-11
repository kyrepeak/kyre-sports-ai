from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

BRANCH = "cfb-game-total-mobile-production-step8-v1"
EXPECTED_HEAD = "0e0e9966e5780711238da92cd1ec412e74c4cd59"
REPO = "https://github.com/kyrepeak/kyre-sports-ai.git"
TEST = "tests/test_cfb_game_total_mobile_production_step8_v1.py"


def _beat(stage: str, detail: object = "") -> None:
    print(
        "CFB_GAME_TOTAL_STEP8_HEARTBEAT="
        + json.dumps({"stage": stage, "detail": detail}, sort_keys=True),
        flush=True,
    )


def _run(cmd: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def _ensure_chromium(root: Path) -> tuple[bool, str]:
    probe = _run(
        [
            sys.executable,
            "-c",
            "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True,args=['--no-sandbox']); b.close(); p.stop(); print('CHROMIUM_READY')",
        ],
        cwd=root,
        timeout=45,
    )
    if probe.returncode == 0:
        return True, "cached"
    _beat("chromium-install", "browser cache miss")
    install = _run([sys.executable, "-m", "playwright", "install", "chromium"], cwd=root, timeout=300)
    if install.returncode != 0:
        return False, ((install.stdout or "") + "\n" + (install.stderr or ""))[-8000:]
    return True, "installed"


def _run_public_with_heartbeat(root: Path) -> dict[str, object]:
    cmd = [
        sys.executable,
        "-m",
        "devsystem.cfb_game_total_mobile_production_step8_v1",
        "--base-url",
        "https://pickvault.streamlit.app",
        "--artifact-dir",
        "artifacts/cfb-game-total-step8",
    ]
    proc = subprocess.Popen(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    started = time.monotonic()
    while proc.poll() is None:
        elapsed = int(time.monotonic() - started)
        _beat("public-browser-alive", {"elapsed_seconds": elapsed, "mode": "single-browser-4-viewports"})
        time.sleep(15)
        if elapsed > 780:
            proc.kill()
            return {"status": "FAIL", "stage": "public-browser-timeout", "elapsed_seconds": elapsed}
    stdout, stderr = proc.communicate()
    output = (stdout or "") + "\n" + (stderr or "")
    if proc.returncode != 0:
        return {"status": "FAIL", "stage": "public-browser", "detail": output[-16000:]}
    if "CFB_GAME_TOTAL_STEP8_PUBLIC_GREEN" not in output:
        return {"status": "FAIL", "stage": "public-marker-missing", "detail": output[-12000:]}
    marker = "CFB_GAME_TOTAL_STEP8_PUBLIC_EVIDENCE="
    rows = [line for line in (stdout or "").splitlines() if line.startswith(marker)]
    if not rows:
        return {"status": "FAIL", "stage": "public-evidence-missing", "detail": output[-12000:]}
    evidence = json.loads(rows[-1][len(marker):])
    viewports = evidence.get("viewports") or {}
    summary = {
        name: {
            "event_id": ((row.get("page1") or {}).get("exact_event_id")),
            "page1_overflow": ((row.get("page1") or {}).get("horizontal_overflow")),
            "page2_overflow": ((row.get("page2") or {}).get("horizontal_overflow")),
            "page2_visible": ((row.get("page2") or {}).get("all_required_visible")),
            "event_preserved": ((row.get("page1") or {}).get("exact_event_id")) == ((row.get("page2") or {}).get("exact_event_id")),
        }
        for name, row in viewports.items()
    }
    return {
        "status": "PUBLIC_GREEN",
        "phoenix_date": evidence.get("phoenix_date"),
        "render_commit": (evidence.get("render_identity") or {}).get("certified_commit"),
        "viewports": summary,
        "github_actions_fallback": evidence.get("github_actions_fallback"),
    }


def execute() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cfb-step8-public-") as tmp:
        root = Path(tmp) / "repo"
        _beat("clone-start", EXPECTED_HEAD)
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
        _beat("identity-green", head)

        tests = _run([sys.executable, "-m", "pytest", "-q", TEST], cwd=root, timeout=240)
        if tests.returncode != 0:
            return {"status": "FAIL", "stage": "static-tests", "head": head, "detail": ((tests.stdout or "") + "\n" + (tests.stderr or ""))[-9000:]}
        _beat("static-green", (tests.stdout or "").strip()[-500:])

        identity = _run([sys.executable, "devsystem/production_identity_verify_v1.py"], cwd=root, timeout=120)
        if identity.returncode != 0:
            return {"status": "FAIL", "stage": "render-identity", "head": head, "detail": ((identity.stdout or "") + "\n" + (identity.stderr or ""))[-9000:]}
        _beat("render-identity-green", "879c28265efde1810a5e30352fa2dcb269c1052a")

        browser_ok, browser_detail = _ensure_chromium(root)
        if not browser_ok:
            return {"status": "FAIL", "stage": "playwright-install", "head": head, "detail": browser_detail}
        _beat("chromium-green", browser_detail)
        _beat("public-browser-start", "single-browser-4-viewports")

        public = _run_public_with_heartbeat(root)
        if public.get("status") != "PUBLIC_GREEN":
            return {"head": head, **public}
        return {
            "status": "PUBLIC_GREEN",
            "head": head,
            "static_tests": (tests.stdout or "").strip()[-1000:],
            "render_identity_green": "DEVSYSTEM_PRODUCTION_IDENTITY_GREEN" in (identity.stdout or ""),
            **public,
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
        threading.Thread(target=worker, daemon=True, name="cfb-step8-public-proof-serial").start()

    return app
