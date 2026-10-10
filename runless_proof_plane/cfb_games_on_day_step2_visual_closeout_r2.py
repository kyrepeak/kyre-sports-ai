from __future__ import annotations

import json
import subprocess
import sys
import time

from . import cfb_games_on_day_step2_visual_closeout as base


class Step2VisualCloseoutR2Failure(RuntimeError):
    pass


def _public_mobile_proof_subprocess() -> dict:
    install = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
        check=False,
    )
    if install.returncode != 0:
        raise Step2VisualCloseoutR2Failure(
            "PLAYWRIGHT_CHROMIUM_INSTALL_FAILED:" + install.stdout[-1600:]
        )

    route = (
        base.PRODUCTION_URL.rstrip("/")
        + "/?ks_sport=College+Football&ks_cfb_market=Game+Total"
        + f"&ks_cfb_game_total_date={base.PRODUCTION_DATE}"
    )
    script = r'''
import json, time
from playwright.sync_api import sync_playwright
from devsystem import browser_qa_v1 as browser_qa

route = __ROUTE__
deadline = time.monotonic() + 420.0
attempts = 0
samples = 0
last = {}
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
    try:
        while time.monotonic() < deadline:
            attempts += 1
            context = browser.new_context(viewport={"width":390,"height":844})
            page = context.new_page()
            try:
                page.goto(route, wait_until="commit", timeout=120000)
                attempt_deadline = time.monotonic() + 28.0
                while time.monotonic() < attempt_deadline:
                    samples += 1
                    for frame in list(page.frames):
                        try:
                            marker = frame.locator('style[data-kyre-cfb-games-on-day-step2-visual="v1"]')
                            strip = frame.locator('[data-testid="gt163-game-strip"][data-step2-visual="v1"]')
                            cards = frame.locator('.gt2-game-card')
                            if marker.count() < 1 or strip.count() < 1 or cards.count() < 1:
                                continue
                            selected = frame.locator('.gt2-game-card.selected[aria-current="true"]')
                            kickoffs = frame.locator('.gt2-kickoff')
                            logos = frame.locator('.gt2-team-logo')
                            fallbacks = frame.locator('.gt2-team-logo-fallback')
                            body = frame.locator("body").inner_text(timeout=5000)
                            runtime_error = str(browser_qa._body_has_forbidden_error(body) or "")
                            kickoff_text = " | ".join(kickoffs.all_inner_texts())
                            strip_overflow = strip.first.evaluate("el => el.scrollWidth > el.clientWidth + 3")
                            document_overflow = frame.evaluate("() => Math.max(document.documentElement.scrollWidth,document.body.scrollWidth) > document.documentElement.clientWidth + 3")
                            selected_visuals = 0
                            if selected.count() == 1:
                                selected_visuals = selected.first.locator('.gt2-team-logo,.gt2-team-logo-fallback').count()
                            last = {
                                "marker":marker.count(),"strip":strip.count(),"cards":cards.count(),
                                "selected":selected.count(),"logos":logos.count(),"fallbacks":fallbacks.count(),
                                "kickoff_text":kickoff_text,"selected_visuals":selected_visuals,
                                "strip_overflow":strip_overflow,"document_overflow":document_overflow,
                                "page_url":page.url,"frame_url":frame.url,"runtime_error":runtime_error,
                            }
                            if (
                                not runtime_error
                                and selected.count() == 1
                                and selected_visuals >= 2
                                and "MST" in kickoff_text
                                and logos.count() >= 2
                                and not strip_overflow
                                and not document_overflow
                            ):
                                print("CFB_GAMES_ON_DAY_STEP2_PUBLIC_PROOF_R2=" + json.dumps({
                                    "status":"GREEN","url":route,"page_url":page.url,"frame_url":frame.url,
                                    "viewport":{"width":390,"height":844},"attempts":attempts,"samples":samples,
                                    "marker_count":marker.count(),"card_count":cards.count(),
                                    "selected_card_count":selected.count(),"selected_visual_count":selected_visuals,
                                    "logo_count":logos.count(),"fallback_count":fallbacks.count(),
                                    "phoenix_time":True,"section_horizontal_overflow":False,
                                    "document_horizontal_overflow":False,"runtime_error":"",
                                    "capture_phase":"pre-page2-handoff",
                                }, sort_keys=True))
                                raise SystemExit(0)
                        except SystemExit:
                            raise
                        except Exception as exc:
                            last = {"frame_error":f"{type(exc).__name__}:{str(exc)[:500]}","page_url":page.url}
                    if "ks_cfb_game_total_event_id=" in page.url and not last.get("marker"):
                        break
                    time.sleep(0.05)
            except SystemExit:
                raise
            except Exception as exc:
                last = {"attempt_error":f"{type(exc).__name__}:{str(exc)[:900]}"}
            finally:
                context.close()
            time.sleep(0.8)
    finally:
        browser.close()
raise RuntimeError("STEP2_PUBLIC_MOBILE_PROOF_R2_TIMEOUT:" + json.dumps(last, sort_keys=True)[:2200])
'''.replace("__ROUTE__", repr(route))
    completed = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=560,
        check=False,
    )
    marker = "CFB_GAMES_ON_DAY_STEP2_PUBLIC_PROOF_R2="
    line = next(
        (row[len(marker):] for row in reversed(completed.stdout.splitlines()) if row.startswith(marker)),
        "",
    )
    if completed.returncode != 0 or not line:
        raise Step2VisualCloseoutR2Failure(
            "PUBLIC_PROOF_R2_SUBPROCESS_FAILED:" + completed.stdout[-3200:]
        )
    payload = json.loads(line)
    if payload.get("status") != "GREEN":
        raise Step2VisualCloseoutR2Failure("PUBLIC_PROOF_R2_NOT_GREEN")
    return payload


def execute(app):
    base._public_mobile_proof_subprocess = _public_mobile_proof_subprocess
    return base.execute(app)


def install_startup(app):
    app.state.cfb_games_on_day_step2_visual_closeout_r2 = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step2_visual_closeout_r2 = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step2_visual_closeout_r2 = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:4800],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP2_VISUAL_CLOSEOUT_R2="
            + json.dumps(app.state.cfb_games_on_day_step2_visual_closeout_r2, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
