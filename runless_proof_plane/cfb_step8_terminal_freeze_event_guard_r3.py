from __future__ import annotations

import json
import subprocess
import sys
import time
from threading import Thread

from playwright.sync_api import sync_playwright

from . import cfb_step8_terminal_freeze_event_guard_r1 as prior

MERGED_SHA = "283151c3792a73520a37b54bb8f480910004b6d6"
CANDIDATE_SHA = "1e6e4f51a8dc9a5cf0efca3b893ed4321eb9785a"
ROUTER_FROM = "2a73aba9b5a746a4e5ab8ab7040210df3e705666"
ROUTER_TO = "f6ac3a2a79f8ff1fde6013b399d24d2ffb0ed744"
THAW_ID = "THAW-CFB-GT-STEP8-PAGE1-EVENT-GUARD-R2"
PRE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-page1-event-guard-r2"
FINAL_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-terminal-freeze-event-guard-r4"


def _ensure_chromium() -> None:
    install = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        text=True,
        capture_output=True,
        timeout=360,
        check=False,
    )
    if install.returncode != 0:
        detail = ((install.stdout or "") + "\n" + (install.stderr or ""))[-12000:]
        raise RuntimeError("STEP8_CHROMIUM_INSTALL_FAILED:" + detail)


def _robust_frame_with_testid(page, testid: str, timeout_seconds: float):
    deadline = time.monotonic() + timeout_seconds
    last = []
    while time.monotonic() < deadline:
        last = []
        for frame in page.frames:
            try:
                count = frame.locator(f'[data-testid="{testid}"]').count()
                body = frame.locator("body").inner_text(timeout=3000)
            except Exception:
                count = 0
                body = ""
            last.append({"url": str(getattr(frame, "url", "") or ""), "count": count, "body": body[:400]})
            if "get this app back up" in body.casefold():
                try:
                    wake = frame.get_by_text("Yes, get this app back up!", exact=False)
                    if wake.count() > 0:
                        wake.first.click()
                        page.wait_for_timeout(3000)
                except Exception:
                    pass
            if count > 0:
                return frame
        page.wait_for_timeout(1000)
    raise prior.TerminalFreezeFailure(
        f"TESTID_NOT_FOUND:{testid}:{json.dumps(last, ensure_ascii=True)}"
    )


def _browser_readback_r4() -> dict:
    outer = prior._route()
    prefix = prior.PRODUCTION_URL.rstrip("/") + "/?"
    direct = outer.replace(prefix, prior.PRODUCTION_URL.rstrip("/") + "/~/+/?", 1)
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        try:
            page = browser.new_page(viewport={"width": 1067, "height": 1536})
            for route_kind, route in (("outer", outer), ("direct", direct)):
                try:
                    page.goto(route, wait_until="domcontentloaded", timeout=120000)
                    frame = _robust_frame_with_testid(page, prior.PAGE1_TESTID, 120)
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.wait_for_timeout(1800)
                    body = frame.locator("body").inner_text(timeout=5000)
                    forbidden = [term for term in prior.FORBIDDEN if term in body.casefold()]
                    cards = frame.locator(f'[data-testid="{prior.PAGE1_TESTID}"] a[data-event-id]')
                    card_count = cards.count()
                    outer_event = prior._event(page.url)
                    frame_event = prior._event(frame.url)
                    if outer_event or frame_event:
                        raise prior.TerminalFreezeFailure(
                            f"PAGE1_AUTO_EVENT_VISIBLE:{outer_event}:{frame_event}"
                        )
                    if card_count < 1:
                        raise prior.TerminalFreezeFailure("PAGE1_CARD_MISSING")
                    if forbidden:
                        raise prior.TerminalFreezeFailure("PAGE1_FORBIDDEN_VISIBLE:" + ",".join(forbidden))

                    first = cards.first
                    selected_event = str(first.get_attribute("data-event-id") or "").strip()
                    if not selected_event:
                        raise prior.TerminalFreezeFailure("PAGE1_CARD_EVENT_ID_MISSING")
                    first.click(timeout=30000)
                    page2 = _robust_frame_with_testid(page, prior.PAGE2_TESTID, 120)
                    page.wait_for_timeout(1200)
                    body2 = page2.locator("body").inner_text(timeout=5000)
                    forbidden2 = [term for term in prior.FORBIDDEN if term in body2.casefold()]
                    if forbidden2:
                        raise prior.TerminalFreezeFailure("PAGE2_FORBIDDEN_VISIBLE:" + ",".join(forbidden2))
                    page2_event = prior._event(page2.url) or prior._event(page.url)
                    if page2_event and page2_event != selected_event:
                        raise prior.TerminalFreezeFailure(
                            f"PAGE2_EVENT_MISMATCH:{selected_event}:{page2_event}"
                        )
                    if page2.locator('[data-testid="gtp2s8-back-to-slate"]').count() < 1:
                        raise prior.TerminalFreezeFailure("PAGE2_BACK_TO_SLATE_MISSING")
                    return {
                        "status": "GREEN",
                        "production_url": outer,
                        "route_kind": route_kind,
                        "viewport": "390x844",
                        "page1_clean_event_query": True,
                        "page1_card_count": card_count,
                        "selected_event_id": selected_event,
                        "page2_live": True,
                        "page2_event_id": page2_event or selected_event,
                        "forbidden_visible": [],
                    }
                except Exception as exc:
                    failures.append({
                        "route_kind": route_kind,
                        "error": type(exc).__name__,
                        "detail": str(exc)[:6000],
                    })
            raise prior.TerminalFreezeFailure(
                "PRODUCTION_READBACK_FAILED:" + json.dumps(failures, ensure_ascii=True)
            )
        finally:
            browser.close()


def _bind_terminal_identity() -> None:
    prior.MERGED_SHA = MERGED_SHA
    prior.CANDIDATE_SHA = CANDIDATE_SHA
    prior.ROUTER_FROM = ROUTER_FROM
    prior.ROUTER_TO = ROUTER_TO
    prior.THAW_ID = THAW_ID
    prior.PRE_OWNER = PRE_OWNER
    prior.FINAL_OWNER = FINAL_OWNER
    prior._browser_readback = _browser_readback_r4


def execute(app):
    _bind_terminal_identity()
    _ensure_chromium()
    return prior.execute(app)


def install_startup(app):
    app.state.cfb_step8_terminal_freeze_event_guard_r4 = {"status": "STARTING"}

    def _worker():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:16000]}
        app.state.cfb_step8_terminal_freeze_event_guard_r4 = result
        print("CFB_STEP8_TERMINAL_FREEZE_EVENT_GUARD_R4=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    @app.on_event("startup")
    def _run():
        Thread(target=_worker, name="cfb-step8-terminal-finalizer-r4", daemon=True).start()

    return app
