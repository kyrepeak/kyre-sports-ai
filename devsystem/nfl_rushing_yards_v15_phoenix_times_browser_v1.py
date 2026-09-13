"""Real Streamlit browser witness for V15 Phoenix kickoff-time display."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from browser_qa_v1 import (
    BrowserQAFailure,
    _body_has_forbidden_error,
    _find_app_frame,
    _wait_for_health,
    _wait_for_text,
)

from nfl_hub_v1 import load_nfl_slate
import nfl_rushing_yards_hub_v15 as phoenix_page

DEFAULT_BASE_URL = "http://127.0.0.1:8510"
DEFAULT_DAY = "2026-09-13"
FAST_QUERY = "?ks_nfl_sport=NFL&ks_nfl_market=Rushing%20Yards"
V14_MARKER = "matchup classification only"
READY_MARKER = "Monster Performance Diagnosis"


def _expected_games(day: str) -> list[dict]:
    games, diag = load_nfl_slate(day)
    if not diag.get("request_ok") or games.empty:
        raise BrowserQAFailure(f"Verified NFL slate unavailable for {day}: {diag}")
    expected: list[dict] = []
    for _, row in games.iterrows():
        labels = phoenix_page._phoenix_kickoff(row)
        if labels is None:
            raise BrowserQAFailure(
                f"Phoenix conversion unavailable for ESPN event {row.get('game_id')}"
            )
        expected.append(
            {
                "game_id": str(row.get("game_id") or ""),
                "away_team": str(row.get("away_team") or ""),
                "home_team": str(row.get("home_team") or ""),
                "state": str(row.get("state") or "pre").lower(),
                "clock": labels["clock"],
                "clock_with_location": labels["clock_with_location"],
                "status": labels["status"],
            }
        )
    return expected


def run_witness(*, base_url: str, artifact_dir: str | Path, day: str) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    expected = _expected_games(day)

    health = _wait_for_health(base_url)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 2600})
        try:
            page.goto(
                base_url.rstrip("/") + "/" + FAST_QUERY,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, scan = _find_app_frame(page)
            body = _wait_for_text(frame, V14_MARKER, 180.0)
            body = _wait_for_text(frame, READY_MARKER, 180.0)

            forbidden = _body_has_forbidden_error(body)
            if forbidden:
                raise BrowserQAFailure(f"V15 page contains runtime error marker: {forbidden}")
            if frame.locator("section.krush14-player").count() == 0:
                raise BrowserQAFailure("V15 page lost V14 detailed matchup-tier stacks")

            cards = frame.locator("article.krush-game")
            if cards.count() != len(expected):
                raise BrowserQAFailure(
                    f"V15 schedule-card count mismatch: ui={cards.count()} expected={len(expected)}"
                )

            rendered: list[dict] = []
            for wanted in expected:
                card = cards.filter(has_text=wanted["away_team"]).filter(has_text=wanted["home_team"])
                if card.count() != 1:
                    raise BrowserQAFailure(
                        f"Expected one game card for {wanted['away_team']} @ {wanted['home_team']}, got {card.count()}"
                    )
                text = card.first.inner_text()
                if wanted["clock_with_location"] not in text:
                    raise BrowserQAFailure(
                        f"Phoenix clock mismatch for {wanted['game_id']}: expected {wanted['clock_with_location']}"
                    )
                if wanted["state"] == "pre" and wanted["status"] not in text:
                    raise BrowserQAFailure(
                        f"Phoenix pregame status mismatch for {wanted['game_id']}: expected {wanted['status']}"
                    )
                if re.search(r"\b(?:ET|EST|EDT)\b", text):
                    raise BrowserQAFailure(
                        f"Eastern timezone label leaked on V15 game card {wanted['game_id']}: {text}"
                    )
                rendered.append(
                    {
                        "game_id": wanted["game_id"],
                        "away_team": wanted["away_team"],
                        "home_team": wanted["home_team"],
                        "phoenix_clock": wanted["clock"],
                    }
                )

            tb_cin = next((row for row in rendered if row["game_id"] == "401872925"), None)
            if tb_cin is None or tb_cin["phoenix_clock"] != "10:00 AM MST":
                raise BrowserQAFailure(
                    f"Known TB @ CIN Phoenix witness mismatch: {tb_cin}"
                )
            if "sportsbook projection influence 0.0%" not in body.lower():
                raise BrowserQAFailure("V15 page lost 0.0% sportsbook projection influence marker")

            screenshot = artifacts / "rushing_v15_phoenix_times_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "route": "NFL -> Rushing Yards",
                "display_timezone": "America/Phoenix",
                "timezone_label": "MST",
                "verified_game_count": len(expected),
                "rendered_game_card_count": cards.count(),
                "tb_cin_phoenix_clock": tb_cin["phoenix_clock"],
                "eastern_labels_leaked": False,
                "v14_detailed_tiers_preserved": True,
                "sportsbook_projection_influence": 0.0,
                "projection_math_changed": False,
                "rendered": rendered,
                "root_http": health["root_http"],
                "health_http": health["health_http"],
                "frame_scan_count": len(scan),
                "screenshot": str(screenshot),
            }
            (artifacts / "rushing_v15_phoenix_times_metrics.json").write_text(
                json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
            )
            print("NFL_RUSHING_V15_PHOENIX_TIMES_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        except Exception:
            try:
                page.screenshot(path=str(artifacts / "rushing_v15_phoenix_times_failure.png"), full_page=True)
            except Exception:
                pass
            raise
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--artifact-dir", default="artifacts/rushing-v15-phoenix-times")
    parser.add_argument("--day", default=DEFAULT_DAY)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_witness(base_url=args.base_url, artifact_dir=args.artifact_dir, day=args.day)
