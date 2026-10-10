from __future__ import annotations

import json
import subprocess
import sys


def _probe() -> dict:
    script = r'''
import json
from playwright.sync_api import sync_playwright
from devsystem import browser_qa_v1 as browser_qa

url = "https://pickvault.streamlit.app/?ks_sport=College+Football&ks_cfb_market=Game+Total&ks_cfb_game_total_date=2026-10-10&ks_cfb_game_total_event_id=401856824"
out = {"url": url, "viewport": {"width": 390, "height": 844}}
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=120000)
        frame, scans = browser_qa._find_app_frame(page)
        body = frame.locator("body").inner_text(timeout=30000)
        scroller = frame.locator(".gt163-game-scroller").first
        cards = frame.locator(".gt163-game-link,.gt163-game-disabled")
        selected = frame.locator(".gt163-game-link.selected")
        out.update({
            "page_url": page.url,
            "frame_url": frame.url,
            "frame_scan": scans,
            "games_text_visible": "GAMES ON THIS DAY" in body.upper(),
            "body_tail": body[-2200:],
            "step1_style_count": frame.locator('style[data-kyre-cfb-games-on-day-step1-layout="v1"]').count(),
            "gt163_wrap_count": frame.locator(".gt163-game-wrap").count(),
            "gt163_scroller_count": frame.locator(".gt163-game-scroller").count(),
            "gt163_card_count": cards.count(),
            "gt163_selected_count": selected.count(),
            "runtime_error": str(browser_qa._body_has_forbidden_error(body) or ""),
        })
        if scroller.count():
            out["styles"] = scroller.evaluate("el => { const s=getComputedStyle(el); return {display:s.display, gridTemplateColumns:s.gridTemplateColumns, overflowX:s.overflowX, scrollWidth:el.scrollWidth, clientWidth:el.clientWidth}; }")
            out["section_horizontal_overflow"] = scroller.evaluate("el => el.scrollWidth > el.clientWidth + 3")
        if cards.count():
            first = cards.first.bounding_box(); outer = scroller.bounding_box() if scroller.count() else None
            out["first_card_width"] = first["width"] if first else None
            out["scroller_width"] = outer["width"] if outer else None
            out["first_card_full_width"] = bool(first and outer and first["width"] >= outer["width"] - 4)
        out["document_widths"] = frame.evaluate("() => ({scrollWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth), clientWidth: document.documentElement.clientWidth})")
    finally:
        browser.close()
print("CFB_GAMES_ON_DAY_STEP1_SAT_DIAGNOSTIC=" + json.dumps(out, sort_keys=True))
'''
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], text=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, timeout=300, check=True)
    completed = subprocess.run([sys.executable, "-c", script], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180, check=False)
    marker = "CFB_GAMES_ON_DAY_STEP1_SAT_DIAGNOSTIC="
    line = next((row[len(marker):] for row in reversed(completed.stdout.splitlines()) if row.startswith(marker)), "")
    if completed.returncode != 0 or not line:
        return {"status": "FAIL", "detail": completed.stdout.splitlines()[-1] if completed.stdout else f"rc={completed.returncode}"}
    payload = json.loads(line); payload["status"] = "GREEN"; return payload


def install_startup(app):
    @app.on_event("startup")
    def _run():
        try: result = _probe()
        except Exception as exc: result = {"status":"FAIL","error":type(exc).__name__,"detail":str(exc)[:2400]}
        print("CFB_GAMES_ON_DAY_STEP1_SAT_DIAGNOSTIC_RESULT=" + json.dumps(result, sort_keys=True, default=str), flush=True)
    return app


__all__ = ["install_startup"]
