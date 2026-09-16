"""Real-browser QA for the CFB Game Total V150 route.

This is deliberately separate from the frozen O/U V38 browser contract. It
proves the user-visible selector routes College Football -> Game Total to the
V150 page itself, rather than certifying a generic router caption.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

import browser_qa_v1 as base

CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
REQUIRED_VISIBLE = (
    "CFB GAME TOTAL • MONSTER DASHBOARD",
    "College Football Game Total",
    "CFB Game Total slate date",
)
FORBIDDEN_VISIBLE = (
    "College Football Game Total — Final",
)


class GameTotalBrowserQAFailure(RuntimeError):
    pass


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
        page = browser.new_page(viewport={"width": 1440, "height": 1400})
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

            # Wait for the CFB market selector to become the second combobox.
            deadline_ms = 45000
            elapsed = 0
            while elapsed < deadline_ms:
                if frame.get_by_role("combobox").count() >= 2:
                    break
                page.wait_for_timeout(1000)
                elapsed += 1000
            else:
                raise GameTotalBrowserQAFailure(
                    "CFB route did not expose the market selector"
                )

            base._choose(page, frame, 1, GAME_TOTAL_MARKET)
            body = base._wait_for_text(
                frame,
                REQUIRED_VISIBLE[0],
                timeout_seconds=60.0,
            )

            missing = [text for text in REQUIRED_VISIBLE if text not in body]
            if missing:
                raise GameTotalBrowserQAFailure(
                    "V150 Game Total visible contract missing: " + " | ".join(missing)
                )

            stale = [text for text in FORBIDDEN_VISIBLE if text in body]
            if stale:
                raise GameTotalBrowserQAFailure(
                    "Legacy Game Total page is still visible: " + " | ".join(stale)
                )

            forbidden_error = base._body_has_forbidden_error(body)
            if forbidden_error:
                raise GameTotalBrowserQAFailure(
                    f"Game Total route runtime error marker: {forbidden_error}"
                )

            screenshot = artifacts / "cfb_game_total_v150_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "sport": CFB_SPORT,
                "market": GAME_TOTAL_MARKET,
                "required_visible": list(REQUIRED_VISIBLE),
                "forbidden_visible": list(FORBIDDEN_VISIBLE),
                "health": health,
                "initial_frame_scan": scans,
                "screenshot": str(screenshot),
            }
            (artifacts / "cfb_game_total_v150.json").write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print("CFB_GAME_TOTAL_V150_BROWSER_GREEN")
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
