"""Real-browser QA for CFB Game Total V184 Step 6 Scoring Creation.

Reuses the certified V163 exact-game selector/browser primitives, then proves
the additive V184 Step 6 accordion on the real Streamlit entrypoint. The check
switches to a second verified matchup, hard-refreshes, and requires the Step 6
visual/data contract to survive without mutating any projection/model output.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from devsystem import browser_qa_v1 as base
from devsystem import cfb_game_total_browser_qa_v4 as selector_qa

CFB_SPORT = selector_qa.CFB_SPORT
GAME_TOTAL_MARKET = selector_qa.GAME_TOTAL_MARKET
ROUTE_QUERY_SPORT = selector_qa.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = selector_qa.ROUTE_QUERY_MARKET
DATE_QUERY_KEY = selector_qa.DATE_QUERY_KEY
CERT_DATE = selector_qa.CERT_DATE
STEP6_TESTID = "gt157-step-6"
STEP6_TILE_TESTID = "gt184-step6-stat-tile"
STEP6_DEPLOYMENT_MARKER = "CFB_GAME_TOTAL_STEP6_V184_DEPLOYMENT_ACTIVE"
REQUIRED_STEP6_VISIBLE = (
    "💥 Scoring Creation",
    "SCORING ENVIRONMENT",
    "MATCHUP READ",
    "BIGGEST ACCELERATOR",
    "BIGGEST SUPPRESSOR",
    "O/U IMPACT",
    "DATA CONFIDENCE",
    "EXPLOSIVE PASS RATE",
    "EXPLOSIVE RUSH RATE",
    "OVERALL EXPLOSIVE RATE",
    "SCORING-OPPORTUNITY CONVERSION",
    "Big-play susceptibility",
    "Red-zone TD rate allowed",
    "SPORTSBOOK INFLUENCE 0.0%",
    "PROJECTION MUTATION OFF",
)
FORBIDDEN_STEP6_VISIBLE = (
    "POINTS / OPPORTUNITY",
    "TD DRIVES",
)


class GameTotalV184Step6BrowserQAFailure(RuntimeError):
    pass


def _step6_snapshot(frame) -> dict:
    step6 = frame.locator(f'details[data-testid="{STEP6_TESTID}"]')
    if step6.count() != 1:
        raise GameTotalV184Step6BrowserQAFailure(
            f"Expected exactly one V184 Step 6 accordion, found {step6.count()}"
        )

    panel = step6.first
    if panel.get_attribute("open") is None:
        raise GameTotalV184Step6BrowserQAFailure(
            "V184 Step 6 accordion is not open on the certified surface"
        )

    marker = str(panel.get_attribute("data-step6-deployment-marker") or "")
    if marker != STEP6_DEPLOYMENT_MARKER:
        raise GameTotalV184Step6BrowserQAFailure(
            f"Wrong Step 6 deployment marker: {marker!r}"
        )

    state = str(panel.get_attribute("data-step6-state") or "")
    if state not in {"READY", "DATA LIMITED"}:
        raise GameTotalV184Step6BrowserQAFailure(
            f"Unexpected Step 6 state: {state!r}"
        )

    try:
        coverage = int(panel.get_attribute("data-step6-coverage") or "0")
        ready_tiles = int(panel.get_attribute("data-step6-ready-tiles") or "0")
    except ValueError as exc:
        raise GameTotalV184Step6BrowserQAFailure(
            "Step 6 coverage/ready-tile attributes are not integers"
        ) from exc

    if not 0 <= coverage <= 100:
        raise GameTotalV184Step6BrowserQAFailure(
            f"Step 6 coverage outside 0..100: {coverage}"
        )
    if not 0 <= ready_tiles <= 12:
        raise GameTotalV184Step6BrowserQAFailure(
            f"Step 6 ready tile count outside 0..12: {ready_tiles}"
        )

    tiles = panel.locator(f'[data-testid="{STEP6_TILE_TESTID}"]')
    tile_count = tiles.count()
    if tile_count != 12:
        raise GameTotalV184Step6BrowserQAFailure(
            f"Expected exactly 12 Step 6 tiles, found {tile_count}"
        )
    browser_ready_tiles = panel.locator(
        f'[data-testid="{STEP6_TILE_TESTID}"][data-ready="true"]'
    ).count()
    if browser_ready_tiles != ready_tiles:
        raise GameTotalV184Step6BrowserQAFailure(
            "Rendered ready-tile count does not match Step 6 contract: "
            f"dom={browser_ready_tiles} attr={ready_tiles}"
        )
    if state == "READY" and (coverage != 100 or ready_tiles != 12):
        raise GameTotalV184Step6BrowserQAFailure(
            f"READY must be 100% / 12 of 12, got {coverage}% / {ready_tiles}"
        )

    text = panel.inner_text(timeout=15000)
    missing = [token for token in REQUIRED_STEP6_VISIBLE if token not in text]
    if missing:
        raise GameTotalV184Step6BrowserQAFailure(
            "Step 6 visible contract missing: " + " | ".join(missing)
        )
    stale = [token for token in FORBIDDEN_STEP6_VISIBLE if token in text]
    if stale:
        raise GameTotalV184Step6BrowserQAFailure(
            "Stale Step 6 metric labels visible: " + " | ".join(stale)
        )
    forbidden_error = base._body_has_forbidden_error(text)
    if forbidden_error:
        raise GameTotalV184Step6BrowserQAFailure(
            f"Step 6 runtime error marker: {forbidden_error}"
        )

    return {
        "state": state,
        "coverage": coverage,
        "ready_tiles": ready_tiles,
        "tile_count": tile_count,
        "deployment_marker": marker,
    }


def run(
    *,
    base_url: str = base.DEFAULT_BASE_URL,
    artifact_dir: str | Path = "artifacts/cfb-game-total-v184-step6-browser",
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
            frame, body, initial_scan = selector_qa._find_v163_frame(page)
            selector_qa._assert_visible_contract(body)
            initial_step6 = _step6_snapshot(frame)

            initial_event = selector_qa._wait_for_event_query(page)
            strip = frame.locator('[data-testid="gt163-game-strip"]')
            links = strip.locator("a.gt163-game-link")
            count = links.count()
            if count < 2:
                raise GameTotalV184Step6BrowserQAFailure(
                    f"Expected at least two verified games on {CERT_DATE}, got {count}"
                )
            if selector_qa._selected_link_event(frame) != initial_event:
                raise GameTotalV184Step6BrowserQAFailure(
                    "Initial selected game does not match persisted event_id"
                )

            target = None
            target_event = ""
            target_label = ""
            for index in range(count):
                candidate = links.nth(index)
                event_id = str(candidate.get_attribute("data-event-id") or "")
                if event_id and event_id != initial_event:
                    target = candidate
                    target_event = event_id
                    target_label = candidate.inner_text().strip()
                    break
            if target is None:
                raise GameTotalV184Step6BrowserQAFailure(
                    "No second exact-event matchup available for Step 6 browser QA"
                )

            target.click(timeout=30000)
            clicked_event = selector_qa._wait_for_event_query(page, target_event)
            frame_after_click, body_after_click, click_scan = selector_qa._find_v163_frame(page)
            selector_qa._assert_visible_contract(body_after_click)
            clicked_step6 = _step6_snapshot(frame_after_click)
            if selector_qa._selected_link_event(frame_after_click) != target_event:
                raise GameTotalV184Step6BrowserQAFailure(
                    "Clicked matchup did not become selected in V184 browser QA"
                )

            away, home = selector_qa._team_names_from_label(target_label)
            if away and away not in body_after_click:
                raise GameTotalV184Step6BrowserQAFailure(
                    f"Clicked away team {away!r} missing from full analysis"
                )
            if home and home not in body_after_click:
                raise GameTotalV184Step6BrowserQAFailure(
                    f"Clicked home team {home!r} missing from full analysis"
                )

            page.reload(wait_until="domcontentloaded", timeout=120000)
            frame_after_reload, body_after_reload, reload_scan = selector_qa._find_v163_frame(page)
            selector_qa._assert_visible_contract(body_after_reload)
            reloaded_event = selector_qa._wait_for_event_query(page, target_event)
            reloaded_step6 = _step6_snapshot(frame_after_reload)
            if selector_qa._selected_link_event(frame_after_reload) != target_event:
                raise GameTotalV184Step6BrowserQAFailure(
                    "Selected event_id did not survive V184 hard refresh"
                )

            screenshot = artifacts / "cfb_game_total_v184_step6_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "health": health,
                "date": CERT_DATE,
                "viewport": {"width": 1067, "height": 1536},
                "game_link_count": count,
                "initial_event_id": initial_event,
                "clicked_event_id": clicked_event,
                "reloaded_event_id": reloaded_event,
                "clicked_label": target_label,
                "initial_step6": initial_step6,
                "clicked_step6": clicked_step6,
                "reloaded_step6": reloaded_step6,
                "initial_frame_scan": initial_scan,
                "click_frame_scan": click_scan,
                "reload_frame_scan": reload_scan,
                "screenshot": str(screenshot),
            }
            (artifacts / "cfb_game_total_v184_step6.json").write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print("CFB_GAME_TOTAL_V184_STEP6_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=base.DEFAULT_BASE_URL)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/cfb-game-total-v184-step6-browser",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
