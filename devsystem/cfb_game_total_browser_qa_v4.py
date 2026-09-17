"""Real-browser QA for CFB Game Total V163 visible game selection.

At the iPad viewport, deep-link to the frozen Game Total route on a known
multi-game Saturday, prove the visible GAMES ON THIS DAY strip, click a second
verified matchup, require the official ESPN event_id query to change, prove the
full analysis follows that matchup, then hard-refresh and require the same game
to remain selected. Frozen V161/V162 visible contracts remain required.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.sync_api import sync_playwright

from devsystem import browser_qa_v1 as base

CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"
DATE_QUERY_KEY = "ks_cfb_game_total_date"
EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"
CERT_DATE = "2026-09-19"
PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V163_PRODUCTION_ACTIVE"
FULL_RENDER_MARKER = "VIEW TOP 5 →"
REQUIRED_VISIBLE = (
    "GAME DAY",
    "GAMES ON THIS DAY",
    "GAME TOTAL ANALYSIS",
    "TEAM EVIDENCE",
    "GAME TOTAL EVIDENCE • STEPS 1–12",
    "FINAL MODEL SUMMARY",
    "TOP-5 SLATE SCANNER",
)
FORBIDDEN_VISIBLE = (
    "CFB OVER / UNDER • MONSTER DASHBOARD",
    "College Football Game Total — Final",
)


class GameTotalV163BrowserQAFailure(RuntimeError):
    pass


def _query_state(page) -> dict[str, list[str]]:
    return parse_qs(urlparse(page.url).query)


def _event_from_query(page) -> str:
    return (_query_state(page).get(EVENT_QUERY_KEY) or [""])[-1]


def _is_v163_surface(body: str) -> bool:
    return (
        PRODUCTION_HEARTBEAT in body
        and "GAMES ON THIS DAY" in body
        and FULL_RENDER_MARKER in body
    )


def _find_v163_frame(page, timeout_seconds: float = 90.0):
    deadline = time.monotonic() + timeout_seconds
    last_scan: list[dict] = []
    while time.monotonic() < deadline:
        scans: list[dict] = []
        for index, frame in enumerate(page.frames):
            try:
                body = frame.locator("body").inner_text(timeout=5000)
            except Exception:
                body = ""
            scans.append({"index": index, "url": frame.url, "body_start": body[:700]})
            if _is_v163_surface(body):
                return frame, body, scans
        last_scan = scans
        page.wait_for_timeout(750)
    raise GameTotalV163BrowserQAFailure(
        "Could not find full V163 Game Total surface: "
        + json.dumps(last_scan, ensure_ascii=False)
    )


def _assert_visible_contract(body: str) -> None:
    missing = [text for text in REQUIRED_VISIBLE if text not in body]
    if missing:
        raise GameTotalV163BrowserQAFailure(
            "V163 visible contract missing: " + " | ".join(missing)
        )
    stale = [text for text in FORBIDDEN_VISIBLE if text in body]
    if stale:
        raise GameTotalV163BrowserQAFailure(
            "Forbidden legacy Game Total content visible: " + " | ".join(stale)
        )
    forbidden_error = base._body_has_forbidden_error(body)
    if forbidden_error:
        raise GameTotalV163BrowserQAFailure(
            f"V163 runtime error marker: {forbidden_error}"
        )


def _wait_for_event_query(page, expected: str | None = None, timeout_seconds: float = 45.0) -> str:
    deadline = time.monotonic() + timeout_seconds
    last = ""
    while time.monotonic() < deadline:
        last = _event_from_query(page)
        if last and (expected is None or last == expected):
            return last
        page.wait_for_timeout(400)
    raise GameTotalV163BrowserQAFailure(
        f"V163 event query did not reach expected={expected!r}; actual={last!r}; url={page.url!r}"
    )


def _selected_link_event(frame) -> str:
    selected = frame.locator('[data-testid="gt163-game-strip"] button.gt163-game-link[aria-current="true"]')
    if selected.count() != 1:
        raise GameTotalV163BrowserQAFailure(
            f"Expected exactly one selected game link, found {selected.count()}"
        )
    return str(selected.first.get_attribute("data-event-id") or "")


def _team_names_from_label(label: str) -> tuple[str, str]:
    text = label.strip().removeprefix("✓ ")
    matchup = text.split(" • ", 1)[-1]
    if " @ " not in matchup:
        return "", ""
    away, home = matchup.split(" @ ", 1)
    return away.strip(), home.strip()


def run(
    *,
    base_url: str = base.DEFAULT_BASE_URL,
    artifact_dir: str | Path = "artifacts/cfb-game-total-browser-qa-v163",
) -> dict:
    artifacts = base._artifact_dir(artifact_dir)
    health = base._wait_for_health(base_url)
    direct_query = urlencode(
        {
            ROUTE_QUERY_SPORT: CFB_SPORT,
            ROUTE_QUERY_MARKET: GAME_TOTAL_MARKET,
            DATE_QUERY_KEY: CERT_DATE,
        }
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1067, "height": 1536})
        try:
            page.goto(
                base_url.rstrip("/") + "/?" + direct_query,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, body, initial_scan = _find_v163_frame(page)
            _assert_visible_contract(body)

            initial_event = _wait_for_event_query(page)
            strip = frame.locator('[data-testid="gt163-game-strip"]')
            links = strip.locator("button.gt163-game-link")
            count = links.count()
            if count < 2:
                raise GameTotalV163BrowserQAFailure(
                    f"Expected at least two verified games on {CERT_DATE}, got {count}"
                )
            if _selected_link_event(frame) != initial_event:
                raise GameTotalV163BrowserQAFailure(
                    "Initial selected link does not match persisted ESPN event_id"
                )

            target_event = ""
            target_label = ""
            target = None
            for index in range(count):
                candidate = links.nth(index)
                event_id = str(candidate.get_attribute("data-event-id") or "")
                if event_id and event_id != initial_event:
                    target_event = event_id
                    target_label = candidate.inner_text().strip()
                    target = candidate
                    break
            if target is None:
                raise GameTotalV163BrowserQAFailure(
                    "No second exact-event matchup was available to click"
                )

            target.click(timeout=30000)
            clicked_event = _wait_for_event_query(page, target_event)
            frame_after_click, body_after_click, click_scan = _find_v163_frame(page)
            _assert_visible_contract(body_after_click)
            if _selected_link_event(frame_after_click) != target_event:
                raise GameTotalV163BrowserQAFailure(
                    "Clicked matchup did not become the selected V163 game card"
                )
            away, home = _team_names_from_label(target_label)
            if away and away not in body_after_click:
                raise GameTotalV163BrowserQAFailure(
                    f"Clicked away team {away!r} not found in full analysis"
                )
            if home and home not in body_after_click:
                raise GameTotalV163BrowserQAFailure(
                    f"Clicked home team {home!r} not found in full analysis"
                )

            page.reload(wait_until="domcontentloaded", timeout=120000)
            frame_after_reload, body_after_reload, reload_scan = _find_v163_frame(page)
            _assert_visible_contract(body_after_reload)
            reloaded_event = _wait_for_event_query(page, target_event)
            if _selected_link_event(frame_after_reload) != target_event:
                raise GameTotalV163BrowserQAFailure(
                    "Selected ESPN event_id did not survive hard refresh"
                )

            screenshot = artifacts / "cfb_game_total_v163_game_selector_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "health": health,
                "date": CERT_DATE,
                "viewport": {"width": 1067, "height": 1536},
                "game_button_count": count,
                "initial_event_id": initial_event,
                "clicked_event_id": clicked_event,
                "reloaded_event_id": reloaded_event,
                "clicked_label": target_label,
                "initial_frame_scan": initial_scan,
                "click_frame_scan": click_scan,
                "reload_frame_scan": reload_scan,
                "screenshot": str(screenshot),
            }
            (artifacts / "cfb_game_total_v163.json").write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print("CFB_GAME_TOTAL_V163_GAME_SELECTOR_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=base.DEFAULT_BASE_URL)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/cfb-game-total-browser-qa-v163",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
