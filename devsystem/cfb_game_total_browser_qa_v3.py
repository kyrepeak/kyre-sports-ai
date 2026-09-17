"""Real-browser QA for the active CFB Game Total V161 route.

This additive successor leaves frozen V160/V153 certs untouched. It reproduces
the real iPad path at 1067x1536: choose College Football -> Game Total, prove
the visible seven-day GAME DAY strip, click a non-selected day, verify the V161
date query changes, hard-refresh, and prove that exact day plus the V161 Game
Total surface survive. The removed Monster masthead and legacy/O-U shells are
forbidden visible content.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

from devsystem import browser_qa_v1 as base

CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
CFB_MARKET_LABEL = "🎯 CFB Market"
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"
DATE_QUERY_KEY = "ks_cfb_game_total_date"
PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE"
REQUIRED_VISIBLE = (
    "GAME DAY",
    "GAME TOTAL ANALYSIS",
    "5M CERTIFIED",
    "TEAM EVIDENCE",
    "GAME TOTAL EVIDENCE • STEPS 1–12",
    "FINAL MODEL SUMMARY",
    "TOP-5 SLATE SCANNER",
)
FULL_RENDER_MARKER = "VIEW TOP 5 →"
FORBIDDEN_VISIBLE = (
    "MONSTER SPORTS INTELLIGENCE",
    "College Football Game Total — Final",
    "CFB OVER / UNDER • MONSTER DASHBOARD",
    "🏟️ Sport",
    "🎯 CFB Market",
)
_DAY_LABEL = re.compile(
    r"^(?:✓\s*)?(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*•\s*"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}$"
)


class GameTotalV161BrowserQAFailure(RuntimeError):
    pass


def _query_state(page) -> dict[str, list[str]]:
    return parse_qs(urlparse(page.url).query)


def _assert_game_total_query(page) -> dict[str, list[str]]:
    parsed = _query_state(page)
    sport = (parsed.get(ROUTE_QUERY_SPORT) or [""])[-1]
    market = (parsed.get(ROUTE_QUERY_MARKET) or [""])[-1]
    if sport != CFB_SPORT or market != GAME_TOTAL_MARKET:
        raise GameTotalV161BrowserQAFailure(
            "V161 Game Total route did not persist exact query state: "
            f"sport={sport!r} market={market!r} url={page.url!r}"
        )
    return parsed


def _selected_date_from_query(page) -> str:
    parsed = _assert_game_total_query(page)
    return (parsed.get(DATE_QUERY_KEY) or [""])[-1]


def _assert_visible_contract(body: str) -> None:
    missing = [text for text in REQUIRED_VISIBLE if text not in body]
    if missing:
        raise GameTotalV161BrowserQAFailure(
            "V161 Game Total visible contract missing: " + " | ".join(missing)
        )
    stale = [text for text in FORBIDDEN_VISIBLE if text in body]
    if stale:
        raise GameTotalV161BrowserQAFailure(
            "Forbidden V161 Game Total content is visible: " + " | ".join(stale)
        )
    forbidden_error = base._body_has_forbidden_error(body)
    if forbidden_error:
        raise GameTotalV161BrowserQAFailure(
            f"V161 Game Total runtime error marker: {forbidden_error}"
        )


def _find_direct_v161_frame(page, timeout_seconds: float = 45.0):
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
            if PRODUCTION_HEARTBEAT in body and FULL_RENDER_MARKER in body:
                return frame, scans
        last_scan = scans
        page.wait_for_timeout(1000)
    raise GameTotalV161BrowserQAFailure(
        "Could not find direct V161 Game Total surface. "
        + json.dumps(last_scan, ensure_ascii=False)
    )


def _day_buttons(frame) -> list[str]:
    try:
        labels = frame.get_by_role("button").all_inner_texts()
    except Exception as exc:
        raise GameTotalV161BrowserQAFailure(
            f"Could not read V161 day buttons: {exc}"
        ) from exc
    day_buttons = [label.strip() for label in labels if _DAY_LABEL.match(label.strip())]
    if len(day_buttons) != 7:
        raise GameTotalV161BrowserQAFailure(
            f"Expected exactly seven visible V161 game-day buttons, got {day_buttons!r}"
        )
    return day_buttons


def _click_different_day(page, frame) -> tuple[str, list[str]]:
    day_buttons = _day_buttons(frame)
    target = next((label for label in day_buttons if not label.startswith("✓")), "")
    if not target:
        raise GameTotalV161BrowserQAFailure("No non-selected V161 game day was clickable")
    frame.get_by_role("button", name=target, exact=True).click(timeout=30000)

    deadline = time.monotonic() + 45.0
    date_after_click = ""
    while time.monotonic() < deadline:
        page.wait_for_timeout(500)
        date_after_click = _selected_date_from_query(page)
        if date_after_click:
            break
    if not date_after_click:
        raise GameTotalV161BrowserQAFailure(
            f"V161 day click did not set {DATE_QUERY_KEY}: {page.url!r}"
        )
    return date_after_click, day_buttons


def run(
    *,
    base_url: str = base.DEFAULT_BASE_URL,
    artifact_dir: str | Path = "artifacts/cfb-game-total-browser-qa-v161",
) -> dict:
    artifacts = base._artifact_dir(artifact_dir)
    health = base._wait_for_health(base_url)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1067, "height": 1536})
        try:
            page.goto(
                base_url.rstrip("/") + "/",
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, initial_scan = base._find_app_frame(page)
            sports = base._read_sport_options(page, frame)
            if CFB_SPORT not in sports:
                raise GameTotalV161BrowserQAFailure(
                    f"College Football selector option missing: {sports!r}"
                )

            base._choose(page, frame, 0, CFB_SPORT)
            cfb_market_combo = frame.get_by_role(
                "combobox",
                name=CFB_MARKET_LABEL,
                exact=True,
            )
            cfb_market_combo.wait_for(state="visible", timeout=45000)
            base._choose(page, frame, 1, GAME_TOTAL_MARKET)

            frame, direct_scan = _find_direct_v161_frame(page, timeout_seconds=90.0)
            body = base._wait_for_text(frame, FULL_RENDER_MARKER, timeout_seconds=90.0)
            _assert_visible_contract(body)
            query_after_selection = _assert_game_total_query(page)
            day_buttons_before = _day_buttons(frame)

            date_after_click, day_buttons = _click_different_day(page, frame)
            frame_after_click, click_scan = _find_direct_v161_frame(page, timeout_seconds=90.0)
            body_after_click = base._wait_for_text(
                frame_after_click,
                FULL_RENDER_MARKER,
                timeout_seconds=90.0,
            )
            _assert_visible_contract(body_after_click)
            _day_buttons(frame_after_click)

            page.reload(wait_until="domcontentloaded", timeout=120000)
            frame_after_reload, reload_scan = _find_direct_v161_frame(
                page,
                timeout_seconds=90.0,
            )
            body_after_reload = base._wait_for_text(
                frame_after_reload,
                FULL_RENDER_MARKER,
                timeout_seconds=90.0,
            )
            _assert_visible_contract(body_after_reload)
            date_after_reload = _selected_date_from_query(page)
            if date_after_reload != date_after_click:
                raise GameTotalV161BrowserQAFailure(
                    "V161 selected game day did not survive hard refresh: "
                    f"clicked={date_after_click!r} reload={date_after_reload!r}"
                )
            day_buttons_after_reload = _day_buttons(frame_after_reload)

            screenshot = artifacts / "cfb_game_total_v161_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "sport": CFB_SPORT,
                "market": GAME_TOTAL_MARKET,
                "health": health,
                "viewport": {"width": 1067, "height": 1536},
                "required_visible": list(REQUIRED_VISIBLE),
                "forbidden_visible": list(FORBIDDEN_VISIBLE),
                "query_after_selection": query_after_selection,
                "date_after_click": date_after_click,
                "date_after_reload": date_after_reload,
                "day_buttons_before": day_buttons_before,
                "day_buttons_clicked_state": day_buttons,
                "day_buttons_after_reload": day_buttons_after_reload,
                "initial_frame_scan": initial_scan,
                "direct_frame_scan": direct_scan,
                "click_frame_scan": click_scan,
                "reload_frame_scan": reload_scan,
                "screenshot": str(screenshot),
            }
            (artifacts / "cfb_game_total_v161.json").write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print("CFB_GAME_TOTAL_V161_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=base.DEFAULT_BASE_URL)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/cfb-game-total-browser-qa-v161",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
