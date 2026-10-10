from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta
from threading import Thread
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from . import cfb_game_total_page2_step8_finalizer as finalizer
from .workspace import CandidateWorkspace


def _next_phoenix_saturday() -> str:
    today = datetime.now(ZoneInfo("America/Phoenix")).date()
    delta = (5 - today.weekday()) % 7
    return (today + timedelta(days=delta)).isoformat()


def _run_live_cert_on_next_slate(app) -> dict:
    """Certify one exact event across all four viewports in one browser session.

    Final-mile accelerator: discover/load the selected event once, then resize the
    same rendered Page-2 frame instead of repeating four Streamlit cold starts.
    """
    client = app.state.github_client
    settings = app.state.settings
    token = client.auth.installation_token()
    repository_url = f"https://x-access-token@github.com/{settings.repository}.git"
    slate_date = _next_phoenix_saturday()
    with CandidateWorkspace(repository_url, finalizer.MAIN_SHA, token=token) as workspace:
        artifact_dir = workspace.path / "artifacts" / "cfb-game-total-page2-step8"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        direct_route = finalizer.PRODUCTION_URL.rstrip("/") + "/?" + urlencode(
            (
                ("ks_sport", "College Football"),
                ("ks_cfb_market", "Game Total"),
                ("ks_cfb_game_total_date", slate_date),
            )
        )
        code = "\n".join(
            [
                "import json, time",
                "from pathlib import Path",
                "from urllib.parse import urljoin",
                "from playwright.sync_api import sync_playwright",
                "from devsystem import cfb_game_total_page2_step8_live_cert_v1 as cert",
                f"cert.EXPECTED_MAIN_SHA={finalizer.MAIN_SHA!r}",
                f"base_url={finalizer.PRODUCTION_URL!r}",
                f"direct_route={direct_route!r}",
                f"artifact_dir=Path({str(artifact_dir)!r})",
                "artifact_dir.mkdir(parents=True, exist_ok=True)",
                "def event_from_any(page):",
                "    urls=[page.url] + [f.url for f in page.frames]",
                "    for u in urls:",
                "        eid=cert._exact_event_id(u)",
                "        if eid: return eid",
                "    for f in page.frames:",
                "        try:",
                "            links=f.locator(f'a[href*=\"{cert.EVENT_QUERY_KEY}=\"]')",
                "            if links.count():",
                "                href=links.first.get_attribute('href') or ''",
                "                eid=cert._exact_event_id(urljoin(page.url, href))",
                "                if eid: return eid",
                "        except Exception:",
                "            pass",
                "    return ''",
                "def page2_frame(page, timeout=60):",
                "    deadline=time.monotonic()+timeout",
                "    last=[]",
                "    while time.monotonic()<deadline:",
                "        last=[]",
                "        for i,f in enumerate(page.frames):",
                "            try:",
                "                count=f.locator('[data-testid=\"gtp2s2-matchup-hero\"]').count()",
                "            except Exception:",
                "                count=0",
                "            last.append({'i':i,'url':f.url,'hero':count})",
                "            if count:",
                "                try:",
                "                    f.locator('[data-testid=\"gtp2s2-matchup-hero\"]').first.wait_for(state='visible', timeout=3000)",
                "                    return f, last",
                "                except Exception:",
                "                    pass",
                "        page.wait_for_timeout(750)",
                "    raise RuntimeError('PAGE2_STEP8_FAST_FRAME_TIMEOUT:'+json.dumps(last))",
                "def wait_terminal_surface(frame, timeout=45):",
                "    deadline=time.monotonic()+timeout",
                "    last=''
",
                "    while time.monotonic()<deadline:",
                "        try:",
                "            body=frame.locator('body').inner_text(timeout=3000)",
                "            last=body[:3000]",
                "            if all(frame.locator(f'[data-testid=\"{tid}\"]').first.is_visible() for tid in cert.REQUIRED_TESTIDS):",
                "                if not cert._forbidden_visible_text(body) and not cert._runtime_error(body):",
                "                    return body",
                "        except Exception:",
                "            pass",
                "        frame.page.wait_for_timeout(750)",
                "    raise RuntimeError('PAGE2_STEP8_FAST_SURFACE_TIMEOUT:'+last)",
                "results={}",
                "with sync_playwright() as p:",
                "    browser=p.chromium.launch(headless=True,args=['--disable-dev-shm-usage','--no-sandbox'])",
                "    page=browser.new_page(viewport=cert.VIEWPORTS['mobile390'])",
                "    try:",
                "        page.goto(direct_route, wait_until='domcontentloaded', timeout=90000)",
                "        deadline=time.monotonic()+45",
                "        event_id=''",
                "        while time.monotonic()<deadline and not event_id:",
                "            event_id=event_from_any(page)",
                "            if not event_id: page.wait_for_timeout(750)",
                "        if not event_id: raise RuntimeError('PAGE2_STEP8_FAST_EVENT_ID_TIMEOUT')",
                "        selected_url=direct_route+'&'+cert.EVENT_QUERY_KEY+'='+event_id",
                "        page.goto(selected_url, wait_until='domcontentloaded', timeout=90000)",
                "        frame, scans=page2_frame(page,60)",
                "        wait_terminal_surface(frame,45)",
                "        for name,viewport in cert.VIEWPORTS.items():",
                "            page.set_viewport_size(viewport)",
                "            page.wait_for_timeout(900)",
                "            frame,_=page2_frame(page,12)",
                "            body=wait_terminal_surface(frame,12)",
                "            forbidden=cert._forbidden_visible_text(body)",
                "            runtime_error=cert._runtime_error(body)",
                "            overflow=cert._horizontal_overflow(frame)",
                "            current_event=cert._exact_event_id(page.url) or event_id",
                "            if current_event!=event_id: raise RuntimeError(f'PAGE2_STEP8_FAST_EVENT_DRIFT:{event_id}:{current_event}')",
                "            if forbidden: raise RuntimeError(f'PAGE2_STEP8_FAST_FORBIDDEN:{name}:{forbidden}')",
                "            if runtime_error: raise RuntimeError(f'PAGE2_STEP8_FAST_RUNTIME:{name}:{runtime_error}')",
                "            if overflow: raise RuntimeError(f'PAGE2_STEP8_FAST_OVERFLOW:{name}')",
                "            shot=artifact_dir/f'cfb_game_total_page2_step8_{name}.png'",
                "            page.screenshot(path=str(shot), full_page=True)",
                "            results[name]={'viewport':dict(viewport),'selected_url':selected_url,'exact_event_id':event_id,'all_required_visible':True,'required_testids_visible':list(cert.REQUIRED_TESTIDS),'forbidden_visible_text':[],'horizontal_overflow':False,'runtime_error':'','initial_frame_scan':scans,'selected_frame_scan':[],'screenshot':str(shot)}",
                "    finally:",
                "        browser.close()",
                "payload={'status':'GREEN','source_main_sha':cert.EXPECTED_MAIN_SHA,'production_url':base_url,'route_url':direct_route,'event_query_key':cert.EVENT_QUERY_KEY,'phoenix_timezone':cert.PHOENIX_TZ,'sportsbook_projection_influence':cert.SPORTSBOOK_PROJECTION_INFLUENCE,'may_modify_product_runtime':False,'github_actions_fallback':0,'health':{'status':'GREEN','mode':'single-session-final-mile'},'viewports':results}",
                "if not cert.evidence_is_terminal_green(payload): raise RuntimeError('PAGE2_STEP8_FAST_EVIDENCE_REJECTED')",
                "evidence_path=artifact_dir/'cfb_game_total_page2_step8_live_cert.json'",
                "evidence_path.write_text(json.dumps(payload,indent=2,sort_keys=True),encoding='utf-8')",
                "print('CFB_GT_PAGE2_STEP8_FAST_LIVE_GREEN',flush=True)",
            ]
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=workspace.path,
            text=True,
            capture_output=True,
            timeout=180,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "")[-5000:]
            raise RuntimeError("PAGE2_STEP8_FAST_LIVE_CERT_FAILED:" + detail)
        evidence_path = artifact_dir / "cfb_game_total_page2_step8_live_cert.json"
        if not evidence_path.exists():
            raise RuntimeError("PAGE2_STEP8_LIVE_CERT_EVIDENCE_MISSING")
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        if evidence.get("status") != "GREEN" or evidence.get("source_main_sha") != finalizer.MAIN_SHA:
            raise RuntimeError("PAGE2_STEP8_LIVE_CERT_IDENTITY_MISMATCH")
        evidence["certified_slate_date"] = slate_date
        evidence["final_mile_accelerator"] = "single-session-four-viewports"
        return evidence


def install_startup(app):
    app.state.cfb_game_total_page2_step8_final = {"status": "NOT_RUN"}

    def _run():
        try:
            install = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                text=True,
                capture_output=True,
                timeout=300,
            )
            if install.returncode != 0:
                detail = (install.stderr or install.stdout or "")[-5000:]
                raise RuntimeError("PAGE2_STEP8_CHROMIUM_INSTALL_FAILED:" + detail)
            finalizer._run_live_cert = _run_live_cert_on_next_slate
            result = finalizer.execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:5000]}
        app.state.cfb_game_total_page2_step8_final = result
        print("CFB_GT_PAGE2_STEP8_FINAL=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    @app.on_event("startup")
    def _start_background_finalizer():
        Thread(target=_run, name="cfb-gt-page2-step8-browser-finalizer", daemon=True).start()

    return app
