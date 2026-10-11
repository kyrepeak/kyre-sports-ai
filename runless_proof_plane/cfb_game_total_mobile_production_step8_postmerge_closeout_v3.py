from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from . import cfb_game_total_mobile_production_step8_postmerge_closeout as core
from . import cfb_game_total_mobile_production_step8_postmerge_closeout_v2 as v2


def _production_ready_subprocess(root):
    phoenix_day = datetime.now(ZoneInfo("America/Phoenix")).date().isoformat()
    query = urlencode(
        {
            "ks_sport": "College Football",
            "ks_cfb_market": "Game Total",
            "ks_cfb_game_total_date": phoenix_day,
        }
    )
    url = f"{core.PRODUCTION_URL}/?{query}"
    script = r'''
import json, sys, time
from playwright.sync_api import sync_playwright
url = sys.argv[1]
phoenix_day = sys.argv[2]
deadline = time.monotonic() + 540
attempt = 0
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    try:
        while time.monotonic() < deadline:
            attempt += 1
            context = browser.new_context(viewport={"width": 390, "height": 1200})
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(10000)
                frames = []
                ready = False
                stale_event = False
                for frame in page.frames:
                    try:
                        body = frame.locator("body").inner_text(timeout=3000)
                    except Exception:
                        body = ""
                    row = {"url": frame.url, "phoenix": "PHOENIX TIME" in body}
                    frames.append(row)
                    if row["phoenix"]:
                        stale_event = "ks_cfb_game_total_event_id=" in frame.url
                        ready = not stale_event
                print("READINESS_HEARTBEAT=" + json.dumps({"attempt": attempt, "ready": ready, "stale_event": stale_event, "phoenix_day": phoenix_day}), flush=True)
                if ready:
                    print("READINESS_GREEN=" + json.dumps({"attempts": attempt, "phoenix_day": phoenix_day, "frames": frames}), flush=True)
                    raise SystemExit(0)
            finally:
                context.close()
            time.sleep(20)
    finally:
        browser.close()
raise SystemExit(2)
'''
    proc = subprocess.Popen(
        [sys.executable, "-c", script, url, phoenix_day],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    green = None
    lines = []
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip()
        lines.append(line)
        if line.startswith("READINESS_HEARTBEAT="):
            try:
                core._beat("production-readiness", json.loads(line.split("=", 1)[1]))
            except Exception:
                pass
        elif line.startswith("READINESS_GREEN="):
            green = json.loads(line.split("=", 1)[1])
    code = proc.wait(timeout=10)
    if code != 0 or green is None:
        raise core.Step8PostmergeCloseoutFailure(
            "PUBLIC_PRODUCTION_DID_NOT_CONVERGE:" + "\n".join(lines[-40:])
        )
    return green


def execute(app):
    original = core._production_ready
    try:
        core._production_ready = _production_ready_subprocess
        return v2.execute(app)
    finally:
        core._production_ready = original


def install_startup(app):
    app.state.cfb_game_total_step8_postmerge_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_step8_postmerge_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_step8_postmerge_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:16000],
            }
        print(
            "CFB_GAME_TOTAL_STEP8_POSTMERGE_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_step8_postmerge_closeout, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
