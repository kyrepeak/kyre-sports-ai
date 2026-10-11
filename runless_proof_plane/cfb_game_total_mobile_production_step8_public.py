from __future__ import annotations

import concurrent.futures
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
VIEWPORTS = ("mobile390", "mobile430", "tablet", "desktop")


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
    install = _run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        cwd=root,
        timeout=300,
    )
    if install.returncode != 0:
        return False, ((install.stdout or "") + "\n" + (install.stderr or ""))[-8000:]
    return True, "installed"


def _viewport_probe(root: Path, name: str) -> dict[str, object]:
    artifact_dir = f"artifacts/cfb-game-total-step8/{name}"
    code = (
        "import json,sys; "
        "from devsystem import cfb_game_total_mobile_production_step8_v1 as m; "
        f"m.VIEWPORTS={{'{name}': m.VIEWPORTS['{name}']}}; "
        f"p=m.run_public(base_url='https://pickvault.streamlit.app', artifact_dir='{artifact_dir}'); "
        "r=p['viewports'][next(iter(p['viewports']))]; "
        "print('STEP8_VIEWPORT_RESULT='+json.dumps({'name':next(iter(p['viewports'])),'phoenix_date':p['phoenix_date'],'render_commit':p['render_identity']['certified_commit'],'page1':r['page1'],'page2':r['page2']},sort_keys=True))"
    )
    proc = _run([sys.executable, "-c", code], cwd=root, timeout=360)
    output = ((proc.stdout or "") + "\n" + (proc.stderr or ""))
    if proc.returncode != 0:
        return {"status": "FAIL", "name": name, "detail": output[-12000:]}
    marker = "STEP8_VIEWPORT_RESULT="
    rows = [line for line in (proc.stdout or "").splitlines() if line.startswith(marker)]
    if not rows:
        return {"status": "FAIL", "name": name, "detail": output[-8000:]}
    payload = json.loads(rows[-1][len(marker):])
    return {"status": "GREEN", **payload}


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

        _beat("viewport-parallel-start", list(VIEWPORTS))
        results: dict[str, dict[str, object]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_viewport_probe, root, name): name for name in VIEWPORTS}
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    row = future.result()
                except Exception as exc:
                    row = {"status": "FAIL", "name": name, "detail": f"{type(exc).__name__}:{exc}"}
                results[name] = row
                _beat("viewport-terminal", {"name": name, "status": row.get("status")})

        failures = {name: row for name, row in results.items() if row.get("status") != "GREEN"}
        if failures:
            return {"status": "FAIL", "stage": "public-browser", "head": head, "failures": failures}

        summary: dict[str, object] = {}
        phoenix_dates: set[str] = set()
        render_commits: set[str] = set()
        for name in VIEWPORTS:
            row = results[name]
            page1 = row.get("page1") or {}
            page2 = row.get("page2") or {}
            phoenix_dates.add(str(row.get("phoenix_date") or ""))
            render_commits.add(str(row.get("render_commit") or ""))
            summary[name] = {
                "event_id": page1.get("exact_event_id"),
                "page1_overflow": page1.get("horizontal_overflow"),
                "page2_overflow": page2.get("horizontal_overflow"),
                "page2_visible": page2.get("all_required_visible"),
                "event_preserved": page1.get("exact_event_id") == page2.get("exact_event_id"),
            }

        if len(phoenix_dates) != 1 or len(render_commits) != 1:
            return {
                "status": "FAIL",
                "stage": "evidence-consistency",
                "head": head,
                "phoenix_dates": sorted(phoenix_dates),
                "render_commits": sorted(render_commits),
            }
        if render_commits != {"879c28265efde1810a5e30352fa2dcb269c1052a"}:
            return {"status": "FAIL", "stage": "render-identity-consistency", "render_commits": sorted(render_commits)}

        return {
            "status": "PUBLIC_GREEN",
            "head": head,
            "static_tests": (tests.stdout or "").strip()[-1000:],
            "render_identity_green": "DEVSYSTEM_PRODUCTION_IDENTITY_GREEN" in (identity.stdout or ""),
            "phoenix_date": next(iter(phoenix_dates)),
            "render_commit": next(iter(render_commits)),
            "viewports": summary,
            "github_actions_fallback": 0,
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
