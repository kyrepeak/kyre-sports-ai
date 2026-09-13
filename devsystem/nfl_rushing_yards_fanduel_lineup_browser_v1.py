"""Real Streamlit browser witness for the full FanDuel Rushing Yards lineup board."""
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

import nfl_rushing_yards_market_api_v1 as market_api

DEFAULT_BASE_URL = "http://127.0.0.1:8507"
DEFAULT_EVENT_ID = "401872925"
FAST_QUERY = "?ks_nfl_sport=NFL&ks_nfl_market=Rushing%20Yards"
LINEUP_MARKER = "FanDuel Rushing Yards • Full Standard Lineup"
READY_MARKER = "Monster Performance Diagnosis"


def _line_text(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    text = f"{number:.1f}"
    return text.rstrip("0").rstrip(".")


def run_witness(*, base_url: str, artifact_dir: str | Path, event_id: str) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    live_market = market_api.fetch_event_market(event_id)
    if live_market.get("ready") is not True or live_market.get("market_available") is not True:
        raise BrowserQAFailure(
            "Live FanDuel Rushing Yards market is unavailable for the lineup witness: "
            + str(live_market.get("reason") or "unknown reason")
        )
    props = [row for row in live_market.get("props") or [] if isinstance(row, dict)]
    if not props:
        raise BrowserQAFailure("Live FanDuel market returned no certified props")

    health = _wait_for_health(base_url)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 2000})
        try:
            page.goto(
                base_url.rstrip("/") + "/" + FAST_QUERY,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, scan = _find_app_frame(page)
            body = _wait_for_text(frame, LINEUP_MARKER, 180.0)
            body = _wait_for_text(frame, READY_MARKER, 180.0)

            forbidden = _body_has_forbidden_error(body)
            if forbidden:
                raise BrowserQAFailure(
                    f"Rushing full-lineup page contains runtime error marker: {forbidden}"
                )
            for raw_marker in (
                '<article class="krush-game"',
                '<article class="krush-proj"',
                '<article class="krush-mkt"',
                '<article class="krush12-card"',
            ):
                if raw_marker in body:
                    raise BrowserQAFailure(
                        f"Rushing full-lineup page leaked literal HTML: {raw_marker}"
                    )

            board = frame.locator(
                'section[aria-label="Full FanDuel Rushing Yards lineup"]'
            )
            if board.count() != 1:
                raise BrowserQAFailure(
                    f"Expected one full FanDuel lineup board, got {board.count()}"
                )
            lineup_cards = board.locator("article.krush12-card")
            if lineup_cards.count() != len(props):
                raise BrowserQAFailure(
                    "Full FanDuel lineup card count does not match live API: "
                    f"ui={lineup_cards.count()} api={len(props)}"
                )

            rendered = []
            market_only = []
            projected = []
            for row in props:
                athlete_id = str(row.get("official_athlete_id") or "").strip()
                team_id = str(row.get("official_team_id") or "").strip()
                if not athlete_id.isdigit() or not team_id.isdigit():
                    raise BrowserQAFailure("Live market prop lost exact ESPN identity")
                card = lineup_cards.filter(has_text=f"ESPN athlete {athlete_id}")
                if card.count() != 1:
                    raise BrowserQAFailure(
                        f"Expected one lineup card for ESPN athlete {athlete_id}, got {card.count()}"
                    )
                text = card.first.inner_text()
                expected_line = _line_text(row.get("line"))
                if expected_line not in text:
                    raise BrowserQAFailure(
                        f"Lineup card for ESPN athlete {athlete_id} is missing live line {expected_line}"
                    )
                if "projection influence 0.0%" not in text.lower():
                    raise BrowserQAFailure(
                        f"Lineup card for ESPN athlete {athlete_id} lost 0.0% projection influence marker"
                    )

                projection_card = frame.locator("article.krush4-card").filter(
                    has_text=f"ESPN athlete {athlete_id}"
                )
                if projection_card.count() == 1:
                    if "PROJECTION AVAILABLE" not in text:
                        raise BrowserQAFailure(
                            f"Projected athlete {athlete_id} is not labeled PROJECTION AVAILABLE"
                        )
                    projected.append(athlete_id)
                elif projection_card.count() == 0:
                    if "MARKET ONLY • NO PROJECTION" not in text:
                        raise BrowserQAFailure(
                            f"Market-only athlete {athlete_id} is not labeled NO PROJECTION"
                        )
                    market_only.append(athlete_id)
                else:
                    raise BrowserQAFailure(
                        f"Ambiguous compact projection cards for ESPN athlete {athlete_id}"
                    )

                rendered.append(
                    {
                        "official_athlete_id": athlete_id,
                        "official_team_id": team_id,
                        "player_name": row.get("player_name"),
                        "line": row.get("line"),
                    }
                )

            if "sportsbook projection influence 0.0%" not in body.lower():
                raise BrowserQAFailure(
                    "Page-level sportsbook projection influence 0.0% marker is missing"
                )

            screenshot = artifacts / "rushing_fanduel_full_lineup_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "route": "NFL -> Rushing Yards",
                "official_event_id": event_id,
                "live_api_prop_count": len(props),
                "rendered_lineup_card_count": lineup_cards.count(),
                "rendered_props": rendered,
                "projected_athlete_ids": projected,
                "market_only_athlete_ids": market_only,
                "literal_html_leaks": [],
                "sportsbook_projection_influence": 0.0,
                "projection_math_changed": False,
                "root_http": health["root_http"],
                "health_http": health["health_http"],
                "frame_scan_count": len(scan),
                "screenshot": str(screenshot),
            }
            (artifacts / "rushing_fanduel_full_lineup_metrics.json").write_text(
                json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
            )
            print("NFL_RUSHING_FANDUEL_FULL_LINEUP_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        except Exception:
            try:
                page.screenshot(
                    path=str(artifacts / "rushing_fanduel_full_lineup_failure.png"),
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
    parser.add_argument("--artifact-dir", default="artifacts/rushing-fanduel-lineup")
    parser.add_argument("--event-id", default=DEFAULT_EVENT_ID)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_witness(
        base_url=args.base_url,
        artifact_dir=args.artifact_dir,
        event_id=args.event_id,
    )
