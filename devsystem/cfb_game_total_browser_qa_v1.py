"""Real-browser QA for the active CFB Game Total V160 route.

This is deliberately separate from the frozen O/U V38 browser contract. It
proves the user-visible selector routes College Football -> Game Total to the
V160 visual-parity page itself, rather than certifying a generic router caption.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

import browser_qa_v1 as base

CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
CFB_MARKET_LABEL = "🎯 CFB Market"
REQUIRED_VISIBLE = (
    "CFB GAME TOTAL • CLEAN PAGE V160 ACTIVE",
    "GAME TOTAL ANALYSIS",
    "TEAM EVIDENCE",
    "GAME TOTAL EVIDENCE • STEPS 1–12",
    "FINAL MODEL SUMMARY",
    "TOP-5 SLATE SCANNER",
    "CFB Game Total slate date",
)
FULL_RENDER_MARKER = "TOP-5 SLATE SCANNER"
FORBIDDEN_VISIBLE = (
    "College Football Game Total — Final",
    ".gt160-masthead{max-width:",
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

            # The initial MLB page can already have two comboboxes. Wait for
            # the CFB-specific market selector so the sport rerun is complete
            # before choosing Game Total.
            cfb_market_combo = frame.get_by_role(
                "combobox",
                name=CFB_MARKET_LABEL,
                exact=True,
            )
            cfb_market_combo.wait_for(
                state="visible",
                timeout=45000,
            )

            base._choose(page, frame, 1, GAME_TOTAL_MARKET)

            # Streamlit can expose the V160 identity badge before the frozen
            # dashboard body has finished streaming. Certify completion using
            # the final visible dashboard section, then inspect the full body.
            body = base._wait_for_text(
                frame,
                FULL_RENDER_MARKER,
                timeout_seconds=90.0,
            )

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
