"""Real-browser QA for the active CFB Game Total V160 route.

This cert reproduces the real iPad path: choose College Football -> Game Total,
verify the exact Game Total query state, hard-refresh, and prove the direct
Monster surface remains active without falling back to the legacy O/U shell.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

import browser_qa_v1 as base

CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
CFB_MARKET_LABEL = "🎯 CFB Market"
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"
REQUIRED_VISIBLE = (
    "CFB GAME TOTAL • CLEAN PAGE V160 ACTIVE",
    "MONSTER",
    "GAME TOTAL ANALYSIS",
    "5M CERTIFIED",
    "TEAM EVIDENCE",
    "GAME TOTAL EVIDENCE • STEPS 1–12",
    "FINAL MODEL SUMMARY",
    "TOP-5 SLATE SCANNER",
)
FULL_RENDER_MARKER = "TOP-5 SLATE SCANNER"
FORBIDDEN_VISIBLE = (
    "College Football Game Total — Final",
    ".gt160-masthead{max-width:",
    "CFB OVER / UNDER • MONSTER DASHBOARD",
    "KYRE SPORTS AI",
    "🏟️ Sport",
    "🎯 CFB Market",
)


class GameTotalBrowserQAFailure(RuntimeError):
    pass


def _assert_game_total_query(page) -> dict[str, list[str]]:
    parsed = parse_qs(urlparse(page.url).query)
    sport = (parsed.get(ROUTE_QUERY_SPORT) or [""])[-1]
    market = (parsed.get(ROUTE_QUERY_MARKET) or [""])[-1]
    if sport != CFB_SPORT or market != GAME_TOTAL_MARKET:
        raise GameTotalBrowserQAFailure(
            "Game Total route did not persist exact query state: "
            f"sport={sport!r} market={market!r} url={page.url!r}"
        )
    return parsed


def _assert_visible_contract(body: str) -> None:
    missing = [text for text in REQUIRED_VISIBLE if text not in body]
    if missing:
        raise GameTotalBrowserQAFailure(
            "V160 Game Total visible contract missing: " + " | ".join(missing)
        )

    stale = [text for text in FORBIDDEN_VISIBLE if text in body]
    if stale:
        raise GameTotalBrowserQAFailure(
            "Forbidden Game Total content is visible: " + " | ".join(stale)
        )

    forbidden_error = base._body_has_forbidden_error(body)
    if forbidden_error:
        raise GameTotalBrowserQAFailure(
            f"Game Total route runtime error marker: {forbidden_error}"
        )


def run(
    *,
    base_url: str = base.DEFAULT_BASE_URL,
    artifact_dir: str | Path = "artifacts/cfb-game-total-browser-qa",
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
            frame, scans = base._find_app_frame(page)
            sports = base._read_sport_options(page, frame)
            if CFB_SPORT not in sports:
                raise GameTotalBrowserQAFailure(
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

            body = base._wait_for_text(
                frame,
                FULL_RENDER_MARKER,
                timeout_seconds=90.0,
            )
            _assert_visible_contract(body)
            query_after_selection = _assert_game_total_query(page)

            # Reproduce the user's actual refresh path. The direct target page
            # intentionally has no generic sport/market selectors after reload.
            page.reload(wait_until="domcontentloaded", timeout=120000)
            frame_after_reload, reload_scans = base._find_app_frame(page)
            body_after_reload = base._wait_for_text(
                frame_after_reload,
                FULL_RENDER_MARKER,
                timeout_seconds=90.0,
            )
            _assert_visible_contract(body_after_reload)
            query_after_reload = _assert_game_total_query(page)

            screenshot = artifacts / "cfb_game_total_v160_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "sport": CFB_SPORT,
                "market": GAME_TOTAL_MARKET,
                "required_visible": list(REQUIRED_VISIBLE),
                "full_render_marker": FULL_RENDER_MARKER,
                "forbidden_visible": list(FORBIDDEN_VISIBLE),
                "health": health,
                "initial_frame_scan": scans,
                "reload_frame_scan": reload_scans,
                "query_after_selection": query_after_selection,
                "query_after_reload": query_after_reload,
                "viewport": {"width": 1067, "height": 1536},
                "screenshot": str(screenshot),
            }
            (artifacts / "cfb_game_total_v160.json").write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print("CFB_GAME_TOTAL_V160_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=base.DEFAULT_BASE_URL)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/cfb-game-total-browser-qa",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
