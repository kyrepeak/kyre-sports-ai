"""CFB Top Picks navigation Step 1 — normal dropdown browser proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from devsystem import browser_qa_v1 as base

CFB_SPORT = "College Football"
CFB_MARKET_LABEL = "🎯 CFB Market"
EXPECTED_CFB_MARKETS = ("Moneyline", "Over/Under", "Game Total", "Top Picks")


def run(*, base_url: str, artifact_dir: str | Path) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    health = base._wait_for_health(base_url)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 390, "height": 844})
        try:
            page.goto(
                base_url.rstrip("/") + "/",
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, scans = base._find_app_frame(page)
            base._choose(page, frame, 0, CFB_SPORT)

            combo = frame.get_by_role(
                "combobox",
                name=CFB_MARKET_LABEL,
                exact=True,
            )
            combo.wait_for(state="visible", timeout=45000)
            combo.click()

            options_locator = page.get_by_role("option")
            options_locator.first.wait_for(state="visible", timeout=10000)
            options = [
                value.strip()
                for value in options_locator.all_inner_texts()
                if value.strip()
            ]

            missing = [value for value in EXPECTED_CFB_MARKETS if value not in options]
            if missing:
                raise AssertionError(
                    f"CFB_TOP_PICKS_NAV_STEP1_OPTIONS_MISSING:{missing!r}; saw={options!r}"
                )
            if options.count("Top Picks") != 1:
                raise AssertionError(
                    f"CFB_TOP_PICKS_NAV_STEP1_TOP_PICKS_COUNT:{options.count('Top Picks')}"
                )

            screenshot = artifacts / "cfb_top_picks_nav_step1_dropdown_green.png"
            page.screenshot(path=str(screenshot), full_page=True)

            result = {
                "status": "GREEN",
                "health": health,
                "viewport": {"width": 390, "height": 844},
                "sport": CFB_SPORT,
                "cfb_market_options": options,
                "expected_markets": list(EXPECTED_CFB_MARKETS),
                "top_picks_count": options.count("Top Picks"),
                "frame_scan": scans,
                "screenshot": str(screenshot),
            }
            (artifacts / "cfb_top_picks_nav_step1_dropdown_evidence.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print("CFB_TOP_PICKS_NAV_STEP1_DROPDOWN_GREEN")
            print("CFB_TOP_PICKS_NAV_STEP1_FROZEN_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        finally:
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8501")
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/cfb-top-picks-nav-step1-dropdown",
    )
    args = parser.parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
