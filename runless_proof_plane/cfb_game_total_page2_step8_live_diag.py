from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta
from threading import Thread
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
from playwright.sync_api import sync_playwright

from devsystem import browser_qa_v1 as base

PRODUCTION_URL = "https://pickvault.streamlit.app"
API_BASE = "https://kyre-sports-api.onrender.com"
EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"
REQUIRED_TESTIDS = (
    "gtp2s2-matchup-hero",
    "gtp2s3-flow",
    "gtp2s4-outlook",
    "gtp2s5-team-snapshot",
    "gtp2s6-trends",
    "gtp2s7-line-lab",
    "gtp2s7-best-bet",
    "gtp2s8-back-to-slate",
    "gtp2s8-final",
)


def _date_candidates() -> list[str]:
    today = datetime.now(ZoneInfo("America/Phoenix")).date()
    return [(today + timedelta(days=i)).isoformat() for i in range(0, 15)]


def _next_saturday() -> str:
    today = datetime.now(ZoneInfo("America/Phoenix")).date()
    return (today + timedelta(days=(5 - today.weekday()) % 7)).isoformat()


def _api_games(game_date: str) -> dict:
    try:
        response = requests.get(
            API_BASE + "/api/v1/cfb/selector/verified-games",
            params={"game_date": game_date},
            timeout=30,
        )
        payload = response.json() if response.ok else {}
        games = payload.get("games") if isinstance(payload, dict) else None
        return {
            "date": game_date,
            "status_code": response.status_code,
            "game_count": len(games) if isinstance(games, list) else 0,
            "synthetic_ids": payload.get("synthetic_ids") if isinstance(payload, dict) else None,
            "projection_weight": payload.get("projection_weight") if isinstance(payload, dict) else None,
            "event_ids": [str(g.get("event_id") or "") for g in (games or [])[:5] if isinstance(g, dict)],
        }
    except Exception as exc:
        return {"date": game_date, "error": type(exc).__name__, "detail": str(exc)[:500], "game_count": 0}


def execute() -> dict:
    install = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        text=True,
        capture_output=True,
        timeout=420,
    )
    if install.returncode != 0:
        raise RuntimeError("CHROMIUM_INSTALL_FAILED:" + (install.stderr or install.stdout or "")[-2000:])

    api_rows = [_api_games(day) for day in _date_candidates()]
    saturday = _next_saturday()
    chosen = next((row for row in api_rows if row.get("date") == saturday and int(row.get("game_count") or 0) > 0), None)
    if chosen is None:
        chosen = next((row for row in api_rows if int(row.get("game_count") or 0) > 0), None)
    if chosen is None:
        return {"status": "NO_LIVE_SLATE", "api_rows": api_rows}

    route = PRODUCTION_URL.rstrip("/") + "/?" + urlencode((
        ("ks_sport", "College Football"),
        ("ks_cfb_market", "Game Total"),
        ("ks_cfb_game_total_date", chosen["date"]),
    ))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(route, wait_until="domcontentloaded", timeout=120000)
            frame, scans = base._find_app_frame(page)
            try:
                frame.locator('[data-testid="gtp2s8-final"]').first.wait_for(state="visible", timeout=90000)
            except Exception:
                pass
            body = frame.locator("body").inner_text(timeout=30000)
            body_lower = body.casefold()
            pending_contexts = []
            start = 0
            while True:
                index = body_lower.find("pending", start)
                if index < 0 or len(pending_contexts) >= 20:
                    break
                pending_contexts.append(body[max(0, index - 160): min(len(body), index + 220)])
                start = index + 7
            pending_elements = frame.evaluate("""() => {
                const visible = (el) => {
                    const s = getComputedStyle(el);
                    const r = el.getBoundingClientRect();
                    return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity || 1) !== 0 && r.width > 0 && r.height > 0;
                };
                const out = [];
                for (const el of document.querySelectorAll('body *')) {
                    const text = (el.innerText || '').trim();
                    if (!text || !text.toLowerCase().includes('pending') || !visible(el)) continue;
                    const childrenWithPending = [...el.children].some(c => ((c.innerText || '').toLowerCase().includes('pending')) && visible(c));
                    if (childrenWithPending) continue;
                    let owner = el;
                    while (owner && owner !== document.body && !owner.getAttribute('data-testid')) owner = owner.parentElement;
                    out.push({
                        tag: el.tagName,
                        text: text.slice(0, 500),
                        class_name: String(el.className || '').slice(0, 300),
                        testid: el.getAttribute('data-testid') || '',
                        owner_testid: owner && owner.getAttribute ? (owner.getAttribute('data-testid') || '') : '',
                        owner_class: owner ? String(owner.className || '').slice(0, 300) : '',
                    });
                    if (out.length >= 20) break;
                }
                return out;
            }""")
            required_counts = {testid: frame.locator(f'[data-testid="{testid}"]').count() for testid in REQUIRED_TESTIDS}
            return {
                "status": "GREEN",
                "chosen": chosen,
                "route": route,
                "page_url": page.url,
                "frame_scans": scans,
                "required_testid_counts": required_counts,
                "pending_count": body_lower.count("pending"),
                "pending_contexts": pending_contexts,
                "pending_elements": pending_elements,
                "body_start": body[:1500],
                "api_rows": api_rows,
            }
        finally:
            browser.close()


def install_startup(app):
    app.state.cfb_game_total_page2_step8_diag = {"status": "NOT_RUN"}

    def _run():
        try:
            result = execute()
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:5000]}
        app.state.cfb_game_total_page2_step8_diag = result
        print("CFB_GT_PAGE2_STEP8_DIAG=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    @app.on_event("startup")
    def _start():
        Thread(target=_run, name="cfb-gt-page2-step8-diag", daemon=True).start()

    return app
