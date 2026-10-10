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


def _date_candidates() -> list[str]:
    today = datetime.now(ZoneInfo("America/Phoenix")).date()
    return [(today + timedelta(days=i)).isoformat() for i in range(0, 15)]


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
            page = browser.new_page(viewport={"width": 430, "height": 932})
            page.goto(route, wait_until="domcontentloaded", timeout=120000)
            frame, scans = base._find_app_frame(page)
            body = frame.locator("body").inner_text(timeout=30000)
            strip_count = frame.locator('[data-testid="gt163-game-strip"]').count()
            link_count = frame.locator(f'a[href*="{EVENT_QUERY_KEY}="]').count()
            return {
                "status": "GREEN",
                "chosen": chosen,
                "route": route,
                "page_url": page.url,
                "frame_scans": scans,
                "strip_count": strip_count,
                "event_link_count": link_count,
                "body_start": body[:3500],
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
