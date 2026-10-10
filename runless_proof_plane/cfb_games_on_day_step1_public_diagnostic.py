from __future__ import annotations

import json
import subprocess
import sys


def _run_probe_subprocess() -> dict:
    script = r'''
import json
from playwright.sync_api import sync_playwright
from devsystem import browser_qa_v1 as browser_qa

url = "https://pickvault.streamlit.app/?ks_jump_sport=CFB&ks_jump_market=Game%20Total"
out = {"url": url, "viewport": {"width": 390, "height": 844}}
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=120000)
        frame, scans = browser_qa._find_app_frame(page)
        body = frame.locator("body").inner_text(timeout=30000)
        out.update({
            "page_url": page.url,
            "frame_url": frame.url,
            "frame_scan": scans,
            "body_prefix": body[:2200],
            "step1_style_count": frame.locator('style[data-kyre-cfb-games-on-day-step1-layout="v1"]').count(),
            "gt163_wrap_count": frame.locator(".gt163-game-wrap").count(),
            "gt163_scroller_count": frame.locator(".gt163-game-scroller").count(),
            "gt163_card_count": frame.locator(".gt163-game-link,.gt163-game-disabled").count(),
            "gt163_selected_count": frame.locator(".gt163-game-link.selected").count(),
            "gtvc4_games_count": frame.locator('[data-testid="gtvc4-games-on-day"]').count(),
            "gtvc4_game_card_count": frame.locator(".gtvc4-game").count(),
            "runtime_error": str(browser_qa._body_has_forbidden_error(body) or ""),
        })
        if out["gt163_scroller_count"]:
            out["gt163_styles"] = frame.locator(".gt163-game-scroller").first.evaluate(
                "el => { const s=getComputedStyle(el); return {display:s.display, gridTemplateColumns:s.gridTemplateColumns, overflowX:s.overflowX, scrollWidth:el.scrollWidth, clientWidth:el.clientWidth}; }"
            )
        if out["gtvc4_games_count"]:
            out["gtvc4_html_prefix"] = frame.locator('[data-testid="gtvc4-games-on-day"]').first.evaluate("el => el.outerHTML.slice(0,1800)")
        out["document_widths"] = frame.evaluate(
            "() => ({scrollWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth), clientWidth: document.documentElement.clientWidth})"
        )
    finally:
        browser.close()
print("CFB_GAMES_ON_DAY_STEP1_DIAGNOSTIC=" + json.dumps(out, sort_keys=True))
'''
    install = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300, check=False)
    if install.returncode != 0:
        return {"status": "FAIL", "stage": "chromium_install", "detail": install.stdout[-1800:]}
    completed = subprocess.run([sys.executable, "-c", script], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180, check=False)
    marker = "CFB_GAMES_ON_DAY_STEP1_DIAGNOSTIC="
    line = next((row[len(marker):] for row in reversed(completed.stdout.splitlines()) if row.startswith(marker)), "")
    if completed.returncode != 0 or not line:
        return {"status": "FAIL", "stage": "browser_probe", "detail": (completed.stdout.splitlines()[-1] if completed.stdout else f"rc={completed.returncode}")}
    payload = json.loads(line)
    payload["status"] = "GREEN"
    return payload


def install_startup(app):
    app.state.cfb_games_on_day_step1_diagnostic = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step1_diagnostic = _run_probe_subprocess()
        except Exception as exc:
            app.state.cfb_games_on_day_step1_diagnostic = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:2400]}
        print("CFB_GAMES_ON_DAY_STEP1_DIAGNOSTIC_RESULT=" + json.dumps(app.state.cfb_games_on_day_step1_diagnostic, sort_keys=True, default=str), flush=True)

    return app


__all__ = ["install_startup"]
