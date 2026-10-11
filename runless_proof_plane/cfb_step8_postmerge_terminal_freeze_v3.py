from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from . import cfb_step8_postmerge_terminal_freeze as base


class Step8PostmergeFreezeV3Failure(RuntimeError):
    pass


def _public_proof() -> dict:
    """Run only the missing post-merge public proof; reuse the exact-head Runless receipt."""
    with tempfile.TemporaryDirectory(prefix="cfb-step8-postmerge-v3-") as tmp:
        root = Path(tmp) / "repo"
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", "main", base.REPO, str(root)],
            text=True,
            capture_output=True,
            timeout=90,
        )
        if clone.returncode != 0:
            raise Step8PostmergeFreezeV3Failure(
                "CLONE_FAILED:" + (clone.stderr or clone.stdout)[-5000:]
            )
        head = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        if head != base.MAIN_SHA:
            raise Step8PostmergeFreezeV3Failure(f"MAIN_DRIFT:{head}")

        # Static exact-head proof already exists in the immutable Runless receipt.
        # Final-mile work is therefore only browser/runtime proof + registry freeze.
        base._ensure_chromium(root)
        code = r'''
import json,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from playwright.sync_api import sync_playwright, Page
from devsystem import cfb_game_total_mobile_production_step8_v1 as m

_ORIGINAL_GOTO = Page.goto
def _bounded_goto(self, url, **kwargs):
    return _ORIGINAL_GOTO(self, url, wait_until='commit', timeout=30000)
Page.goto = _bounded_goto

today = datetime.now(ZoneInfo(m.PHOENIX_TZ)).date()
first = today + timedelta(days=((5 - today.weekday()) % 7 or 7))
upcoming = None
for week in range(4):
    day = first + timedelta(days=7*week)
    try:
        r = requests.get(
            m.RENDER_URL.rstrip('/') + '/api/v1/cfb/selector/verified-games',
            params={'game_date': day.isoformat()},
            timeout=15,
        )
        payload = r.json() if r.ok else {}
    except Exception:
        payload = {}
    games = payload.get('games') if isinstance(payload, dict) else None
    if isinstance(games, list) and games:
        upcoming = day
        break
if upcoming is None:
    upcoming = first
m.HANDOFF_CERT_DAY = upcoming.isoformat()
artifacts = Path('artifacts/cfb-game-total-step8-postmerge-v3')
artifacts.mkdir(parents=True, exist_ok=True)
identity = m.verify_render_identity()
rows = {}
readiness = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True,args=['--disable-dev-shm-usage','--no-sandbox'])
    try:
        probe = browser.new_page(viewport={'width':390,'height':844})
        ready = False
        try:
            for attempt in range(1,4):
                try:
                    probe.goto(m.page1_route(m.PRODUCTION_URL))
                    time.sleep(1.5)
                    url_events = {m._event_from_url(probe.url)}
                    for f in probe.frames:
                        url_events.add(m._event_from_url(str(getattr(f,'url','') or '')))
                    url_events.discard('')
                    _, scans = m._find_cfb_frame(
                        probe,
                        required_markers=m.PAGE1_FRAME_MARKERS,
                        required_testids=(m.PHOENIX_DAY_TESTID,m.PAGE1_TESTID),
                        timeout_seconds=20.0,
                    )
                    fresh = not url_events
                    readiness.append({
                        'attempt':attempt,
                        'fresh':fresh,
                        'stale_event_ids':sorted(url_events),
                        'frame_count':len(scans),
                    })
                    if fresh:
                        ready = True
                        break
                except Exception as exc:
                    readiness.append({
                        'attempt':attempt,
                        'fresh':False,
                        'error':type(exc).__name__,
                        'detail':str(exc)[:1200],
                    })
                time.sleep(4)
        finally:
            probe.close()
        if not ready:
            raise RuntimeError('PICKVAULT_DID_NOT_CONVERGE:' + json.dumps(readiness,sort_keys=True))

        for name, viewport in m.VIEWPORTS.items():
            page = browser.new_page(viewport=viewport)
            try:
                page1, selected_url, event_id = m._page1_result(
                    page, name, artifacts, m.PRODUCTION_URL
                )
                preselect_events = {m._event_from_url(page.url)}
                for f in page.frames:
                    preselect_events.add(m._event_from_url(str(getattr(f,'url','') or '')))
                preselect_events.discard('')
                if preselect_events:
                    raise RuntimeError(
                        'PAGE1_AUTO_EVENT_PRESENT:' + name + ':'
                        + json.dumps(sorted(preselect_events))
                    )
                page2 = m._page2_result(page,name,selected_url,event_id,artifacts)
                if page1.get('horizontal_overflow') is not False or page2.get('horizontal_overflow') is not False:
                    raise RuntimeError('OVERFLOW:' + name)
                if page2.get('all_required_visible') is not True:
                    raise RuntimeError('PAGE2_NOT_VISIBLE:' + name)
                if set(page2.get('observed_event_ids') or []) != {event_id}:
                    raise RuntimeError('EVENT_DRIFT:' + name)
                rows[name] = {
                    'event_id':event_id,
                    'page1_overflow':page1.get('horizontal_overflow'),
                    'page2_overflow':page2.get('horizontal_overflow'),
                    'page2_visible':page2.get('all_required_visible'),
                }
            finally:
                page.close()
    finally:
        browser.close()
print('CFB_STEP8_POSTMERGE_PUBLIC_V3=' + json.dumps({
    'status':'PUBLIC_GREEN',
    'main_sha':'e6490b5e52a32c16b283cd676fb0c51c02e2b7df',
    'phoenix_today':today.isoformat(),
    'upcoming_slate_day':upcoming.isoformat(),
    'render_identity':identity,
    'viewports':rows,
    'readiness_attempts':readiness,
    'static_proof_reused':True,
    'github_actions_fallback':0,
},sort_keys=True))
'''
        proof = base._run([sys.executable, "-c", code], cwd=root, timeout=300)
        output = (proof.stdout or "") + "\n" + (proof.stderr or "")
        if proof.returncode != 0:
            raise Step8PostmergeFreezeV3Failure(
                "POSTMERGE_PUBLIC_RED:" + output[-18000:]
            )
        marker = "CFB_STEP8_POSTMERGE_PUBLIC_V3="
        receipts = [
            line for line in (proof.stdout or "").splitlines() if line.startswith(marker)
        ]
        if not receipts:
            raise Step8PostmergeFreezeV3Failure(
                "POSTMERGE_PUBLIC_RECEIPT_MISSING:" + output[-8000:]
            )
        receipt = json.loads(receipts[-1][len(marker):])
        if receipt.get("status") != "PUBLIC_GREEN" or receipt.get("main_sha") != base.MAIN_SHA:
            raise Step8PostmergeFreezeV3Failure("POSTMERGE_PUBLIC_RECEIPT_REJECTED")
        return receipt


def execute(app) -> dict:
    runless_receipt = base._verify_merge_and_runless(app.state.github_client)
    public_receipt = _public_proof()
    return base._freeze(app, public_receipt, runless_receipt)


def install_startup(app):
    app.state.cfb_step8_postmerge_terminal_freeze_v3 = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _start():
        def worker():
            try:
                app.state.cfb_step8_postmerge_terminal_freeze_v3 = execute(app)
            except Exception as exc:
                app.state.cfb_step8_postmerge_terminal_freeze_v3 = {
                    "status": "FAIL",
                    "error": type(exc).__name__,
                    "detail": str(exc)[:22000],
                }
            print(
                "CFB_STEP8_POSTMERGE_TERMINAL_FREEZE_V3="
                + json.dumps(app.state.cfb_step8_postmerge_terminal_freeze_v3, sort_keys=True, default=str),
                flush=True,
            )
        threading.Thread(
            target=worker,
            daemon=True,
            name="cfb-step8-postmerge-terminal-freeze-v3",
        ).start()

    return app
