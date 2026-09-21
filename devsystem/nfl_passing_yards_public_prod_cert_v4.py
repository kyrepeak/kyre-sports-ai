"""Targeted read-only public cert for layered NFL Passing Yards V43."""
from __future__ import annotations

from pathlib import Path
import json
from playwright.sync_api import sync_playwright
import nfl_passing_yards_public_prod_cert_v1 as base

REQUIRED = (
    "Passing Yards",
    "LIVE DATA • MODEL FROZEN",
    "Overview",
    "Why",
    "Matchup",
    "Trends",
    "Market",
    "Deep Data",
    "Open Full Breakdown",
)
FORBIDDEN = (
    "Passing Yards • Combined Player Cards",
)

def run_public_cert(*, production_url: str, api_url: str, artifact_dir: str | Path = "artifacts/nfl-passing-yards-public-prod"):
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    health = base._wait_for_public_streamlit(production_url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        try:
            page.goto(production_url, wait_until="domcontentloaded", timeout=120000)
            frame, _ = base._find_app_frame(page)

            sport = frame.get_by_role("combobox", name="🏟️ Sport", exact=True)
            sport.wait_for(state="visible", timeout=60000)
            base._choose(page, sport, "NFL")

            page.wait_for_timeout(1200)
            frame, _ = base._find_app_frame(page)
            market = frame.get_by_role("combobox", name="🎯 NFL Market", exact=True)
            market.wait_for(state="visible", timeout=60000)
            base._choose(page, market, "Passing Yards")

            page.wait_for_timeout(1500)
            frame, _ = base._find_app_frame(page)
            base._wait_text(frame, "LIVE DATA • MODEL FROZEN", 180000)
            body = base._body(frame)
            base._assert_no_runtime_error(body, "layered NFL Passing Yards public route")

            missing = [m for m in REQUIRED if m.casefold() not in body.casefold()]
            legacy = [m for m in FORBIDDEN if m.casefold() in body.casefold()]
            if missing:
                raise base.PublicProductionCertFailure("missing layered markers: " + json.dumps(missing))
            if legacy:
                raise base.PublicProductionCertFailure("legacy presentation visible: " + json.dumps(legacy))

            screenshot = artifacts / "nfl_passing_yards_layered_public_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "production_url": production_url,
                "api_url": api_url,
                "streamlit_health": health,
                "required_markers": list(REQUIRED),
                "legacy_markers_absent": list(FORBIDDEN),
            }
            print("NFL_PASSING_YARDS_LAYERED_PUBLIC_PRODUCTION_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        finally:
            browser.close()

if __name__ == "__main__":
    args = base._parse_args()
    run_public_cert(
        production_url=args.production_url,
        api_url=args.api_url,
        artifact_dir=args.artifact_dir,
    )
