"""Real-browser QA for CFB Game Total V164 exact team logos."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from devsystem import browser_qa_v1 as base
from devsystem import cfb_game_total_browser_qa_v4 as v163

CERT_DATE = "2026-09-19"
CERT_EVENT_ID = "401869940"
AWAY_TEAM = "Coastal Carolina"
HOME_TEAM = "Delaware"
AWAY_TEAM_ID = "324"
HOME_TEAM_ID = "48"
EXPECTED_LOGO_SUFFIXES = (f"/{AWAY_TEAM_ID}.png", f"/{HOME_TEAM_ID}.png")


class GameTotalV164LogoQAFailure(RuntimeError):
    pass


def _image_state(locator) -> dict:
    return locator.evaluate(
        """img => ({
            src: img.currentSrc || img.src || "",
            complete: Boolean(img.complete),
            naturalWidth: Number(img.naturalWidth || 0),
            naturalHeight: Number(img.naturalHeight || 0)
        })"""
    )


def _assert_logo_group(frame, selector: str, label: str) -> list[dict]:
    images = frame.locator(selector)
    if images.count() != 2:
        raise GameTotalV164LogoQAFailure(
            f"{label} expected exactly two logo images; found {images.count()}"
        )
    states = [_image_state(images.nth(i)) for i in range(images.count())]
    sources = [str(row["src"]) for row in states]
    for suffix in EXPECTED_LOGO_SUFFIXES:
        if not any(src.endswith(suffix) for src in sources):
            raise GameTotalV164LogoQAFailure(
                f"{label} missing exact ESPN logo {suffix}: {sources}"
            )
    for row in states:
        if not row["complete"] or row["naturalWidth"] <= 0 or row["naturalHeight"] <= 0:
            raise GameTotalV164LogoQAFailure(
                f"{label} logo did not load as an image: {row}"
            )
    return states


def run(
    *,
    base_url: str = base.DEFAULT_BASE_URL,
    artifact_dir: str | Path = "artifacts/cfb-game-total-v164-logos",
) -> dict:
    artifacts = base._artifact_dir(artifact_dir)
    health = base._wait_for_health(base_url)
    query = urlencode(
        {
            v163.ROUTE_QUERY_SPORT: v163.CFB_SPORT,
            v163.ROUTE_QUERY_MARKET: v163.GAME_TOTAL_MARKET,
            v163.DATE_QUERY_KEY: CERT_DATE,
            v163.EVENT_QUERY_KEY: CERT_EVENT_ID,
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
                base_url.rstrip("/") + "/?" + query,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, body, scans = v163._find_v163_frame(page)
            v163._assert_visible_contract(body)
            event_id = v163._wait_for_event_query(page, CERT_EVENT_ID)
            if AWAY_TEAM not in body or HOME_TEAM not in body:
                raise GameTotalV164LogoQAFailure(
                    f"expected certified matchup not visible: {AWAY_TEAM} @ {HOME_TEAM}"
                )

            header = _assert_logo_group(frame, "img.gt159-logo", "matchup header")
            evidence = _assert_logo_group(
                frame,
                "img.gt160-evidence-logo",
                "team evidence",
            )

            screenshot = artifacts / "cfb_game_total_v164_exact_team_logos_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "health": health,
                "date": CERT_DATE,
                "event_id": event_id,
                "away_team": AWAY_TEAM,
                "away_team_id": AWAY_TEAM_ID,
                "home_team": HOME_TEAM,
                "home_team_id": HOME_TEAM_ID,
                "header_logos": header,
                "evidence_logos": evidence,
                "frame_scan_count": len(scans),
                "screenshot": str(screenshot),
            }
            (artifacts / "cfb_game_total_v164_logo_evidence.json").write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return result
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=base.DEFAULT_BASE_URL)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/cfb-game-total-v164-logos",
    )
    args = parser.parse_args()
    result = run(base_url=args.base_url, artifact_dir=args.artifact_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    print("CFB_GAME_TOTAL_V164_EXACT_TEAM_LOGOS_GREEN")


if __name__ == "__main__":
    main()
