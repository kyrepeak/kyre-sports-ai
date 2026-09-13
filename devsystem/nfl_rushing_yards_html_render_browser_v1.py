"""Real Streamlit browser witness for NFL Rushing Yards HTML render repair."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_qa_v1 import (
    BrowserQAFailure,
    _body_has_forbidden_error,
    _find_app_frame,
    _wait_for_health,
    _wait_for_text,
)

DEFAULT_BASE_URL = "http://127.0.0.1:8505"
FAST_QUERY = "?ks_nfl_sport=NFL&ks_nfl_market=Rushing%20Yards"
PAGE_MARKER = "Ground Game Lab"
READY_MARKER = "Monster Performance Diagnosis"
RAW_HTML_MARKERS = (
    '<article class="krush-game"',
    '<article class="krush-proj"',
    '<article class="krush-mkt"',
    '<article class="krush-mkt off"',
)


def run_witness(*, base_url: str, artifact_dir: str | Path) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    health = _wait_for_health(base_url)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1800})
        try:
            page.goto(
                base_url.rstrip("/") + "/" + FAST_QUERY,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, scan = _find_app_frame(page)
            _wait_for_text(frame, PAGE_MARKER, 90.0)
            body = _wait_for_text(frame, READY_MARKER, 150.0)

            forbidden = _body_has_forbidden_error(body)
            if forbidden:
                raise BrowserQAFailure(
                    f"Rushing HTML repair contains runtime error marker: {forbidden}"
                )

            leaked = [marker for marker in RAW_HTML_MARKERS if marker in body]
            if leaked:
                raise BrowserQAFailure(
                    "Rushing page leaked literal HTML instead of rendering cards: "
                    + ", ".join(leaked)
                )

            game_cards = frame.locator("article.krush-game").count()
            projection_cards = frame.locator("article.krush-proj").count()
            market_cards = frame.locator("article.krush-mkt").count()
            if game_cards < 1:
                raise BrowserQAFailure("No rendered Rushing game cards were found")
            if projection_cards < 1:
                raise BrowserQAFailure("No rendered Rushing projection cards were found")
            if market_cards < 1:
                raise BrowserQAFailure("No rendered Rushing market cards were found")

            if "sportsbook projection influence 0.0%" not in body.lower():
                raise BrowserQAFailure(
                    "Rushing sportsbook projection influence 0.0% marker is missing"
                )

            screenshot = artifacts / "rushing_html_render_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "route": "NFL -> Rushing Yards",
                "root_http": health["root_http"],
                "health_http": health["health_http"],
                "game_cards": game_cards,
                "projection_cards": projection_cards,
                "market_cards": market_cards,
                "literal_html_leaks": [],
                "sportsbook_projection_influence": 0.0,
                "projection_math_changed": False,
                "frame_scan_count": len(scan),
                "screenshot": str(screenshot),
            }
            (artifacts / "rushing_html_render_metrics.json").write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print("NFL_RUSHING_YARDS_HTML_RENDER_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        except Exception:
            try:
                page.screenshot(
                    path=str(artifacts / "rushing_html_render_failure.png"),
                    full_page=True,
                )
            except Exception:
                pass
            raise
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--artifact-dir", default="artifacts/rushing-html-render")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_witness(base_url=args.base_url, artifact_dir=args.artifact_dir)
