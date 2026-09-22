"""Branch-local browser proof for the CFB Game Total activation chain.

This legacy-named QA preserves the V152 activation route while allowing its
certified additive successor. The real app must reach College Football -> Game
Total and expose the current V161 production heartbeat through Router V156.
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
HEARTBEAT = "CFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE"


class V152ActivationFailure(RuntimeError):
    pass


def run(
    *,
    base_url: str = base.DEFAULT_BASE_URL,
    artifact_dir: str | Path = "artifacts/cfb-game-total-v152-activation",
) -> dict:
    artifacts = base._artifact_dir(artifact_dir)
    health = base._wait_for_health(base_url)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        try:
            page.goto(
                base_url.rstrip("/") + "/",
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, scans = base._find_app_frame(page)
            sports = base._read_sport_options(page, frame)
            if CFB_SPORT not in sports:
                raise V152ActivationFailure(
                    f"College Football selector option missing: {sports!r}"
                )

            base._choose(page, frame, 0, CFB_SPORT)
            market_combo = frame.get_by_role(
                "combobox",
                name=CFB_MARKET_LABEL,
                exact=True,
            )
            market_combo.wait_for(state="visible", timeout=45000)
            base._choose(page, frame, 1, GAME_TOTAL_MARKET)

            body = base._wait_for_text(frame, HEARTBEAT, timeout_seconds=60.0)
            if HEARTBEAT not in body:
                raise V152ActivationFailure("V161 production heartbeat is not visible")

            forbidden_error = base._body_has_forbidden_error(body)
            if forbidden_error:
                raise V152ActivationFailure(
                    f"Game Total route runtime error marker: {forbidden_error}"
                )

            screenshot = artifacts / "cfb_game_total_v152_activation_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "sport": CFB_SPORT,
                "market": GAME_TOTAL_MARKET,
                "heartbeat": HEARTBEAT,
                "health": health,
                "initial_frame_scan": scans,
                "screenshot": str(screenshot),
            }
            (artifacts / "cfb_game_total_v152_activation.json").write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print("CFB_GAME_TOTAL_V152_ACTIVATION_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=base.DEFAULT_BASE_URL)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/cfb-game-total-v152-activation",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
