"""Branch-local browser proof for the CFB Game Total activation chain.

This legacy-named QA preserves the V152 activation route while allowing its
certified additive successor. The real app must reach College Football -> Game
Total through the canonical query route and expose the current V161 production
heartbeat without depending on historical root-selector ordering.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from playwright.sync_api import sync_playwright

import browser_qa_v1 as base

CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
HEARTBEAT = "CFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE"


class V152ActivationFailure(RuntimeError):
    pass


def _find_game_total_heartbeat_frame(page, timeout_seconds: float = 60.0):
    """Find the direct Game Total frame by its certified V161 heartbeat."""
    deadline = time.monotonic() + timeout_seconds
    last_scan: list[dict] = []
    while time.monotonic() < deadline:
        scans: list[dict] = []
        for index, frame in enumerate(page.frames):
            try:
                body = frame.locator("body").inner_text(timeout=5000)
            except Exception:
                body = ""
            scans.append(
                {
                    "index": index,
                    "url": frame.url,
                    "body_start": body[:500],
                }
            )
            if HEARTBEAT in body:
                return frame, scans, body
        last_scan = scans
        page.wait_for_timeout(1000)
    raise V152ActivationFailure(
        "V161 production heartbeat was not found on the canonical Game Total route. "
        + json.dumps(last_scan, ensure_ascii=False)
    )


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
            # The terminal runtime can put page-local controls before any global
            # sport selector. Enter through the certified query contract instead
            # of treating combobox position as route identity.
            page.goto(
                base._cfb_game_total_url(base_url),
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, scans, body = _find_game_total_heartbeat_frame(page)
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
