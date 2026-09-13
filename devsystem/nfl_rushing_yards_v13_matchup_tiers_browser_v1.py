"""Real Streamlit browser witness for V13 Rushing Yards matchup tiers."""
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

import nfl_rushing_yards_context_api_v1 as context_api
import nfl_rushing_yards_hub_v13 as tiers_page
import nfl_rushing_yards_market_api_v1 as market_api

DEFAULT_BASE_URL = "http://127.0.0.1:8508"
DEFAULT_EVENT_ID = "401872925"
FAST_QUERY = "?ks_nfl_sport=NFL&ks_nfl_market=Rushing%20Yards"
V13_MARKER = "FanDuel Rushing Yards • Favorable First"
READY_MARKER = "Monster Performance Diagnosis"
ATHLETE_RE = re.compile(r"ESPN athlete\s+(\d+)")


def _line_text(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    text = f"{number:.1f}"
    return text.rstrip("0").rstrip(".")


def _expected_rows(context: dict, market: dict) -> list[dict]:
    teams = tiers_page.prior._team_map(context)
    expected: list[dict] = []
    for row in market.get("props") or []:
        if not isinstance(row, dict):
            continue
        athlete_id = tiers_page.prior._safe(row.get("official_athlete_id"), "")
        team_id = tiers_page.prior._safe(row.get("official_team_id"), "")
        if not athlete_id.isdigit() or not team_id.isdigit():
            raise BrowserQAFailure("Live FanDuel prop lost exact ESPN athlete/team identity")
        team = teams.get(team_id)
        if not isinstance(team, dict):
            raise BrowserQAFailure(f"Certified context missing exact ESPN team {team_id}")
        opponent_id = tiers_page.prior._safe(team.get("opponent_official_team_id"), "")
        opponent = teams.get(opponent_id)
        if not opponent_id.isdigit() or not isinstance(opponent, dict):
            raise BrowserQAFailure(f"Certified context missing opponent for exact ESPN team {team_id}")
        grade = tiers_page._matchup_tier(team, opponent)
        expected.append(
            {
                "official_athlete_id": athlete_id,
                "official_team_id": team_id,
                "player_name": row.get("player_name"),
                "line": row.get("line"),
                "tier": grade["tier"],
                "score": grade["score"],
            }
        )
    expected.sort(
        key=lambda item: (
            tiers_page.TIER_ORDER.get(item["tier"], 1),
            item["official_team_id"],
            str(item.get("player_name") or ""),
        )
    )
    return expected


def run_witness(*, base_url: str, artifact_dir: str | Path, event_id: str) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    context = context_api.fetch_event_context(event_id)
    if context.get("ready") is not True:
        raise BrowserQAFailure(
            "Certified Rushing context unavailable for V13 witness: "
            + str(context.get("reason") or "unknown reason")
        )
    market = market_api.fetch_event_market(event_id)
    if market.get("ready") is not True or market.get("market_available") is not True:
        raise BrowserQAFailure(
            "Live FanDuel Rushing market unavailable for V13 witness: "
            + str(market.get("reason") or "unknown reason")
        )
    expected = _expected_rows(context, market)
    if not expected:
        raise BrowserQAFailure("V13 witness has no exact-ID live FanDuel props")

    health = _wait_for_health(base_url)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 2200})
        try:
            page.goto(
                base_url.rstrip("/") + "/" + FAST_QUERY,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, scan = _find_app_frame(page)
            body = _wait_for_text(frame, V13_MARKER, 180.0)
            body = _wait_for_text(frame, READY_MARKER, 180.0)

            forbidden = _body_has_forbidden_error(body)
            if forbidden:
                raise BrowserQAFailure(f"V13 page contains runtime error marker: {forbidden}")
            if f"official ESPN event {event_id}" not in body:
                raise BrowserQAFailure(f"V13 page did not select exact ESPN event {event_id}")

            board = frame.locator('section[aria-label="Full FanDuel Rushing Yards lineup"]')
            if board.count() != 1:
                raise BrowserQAFailure(f"Expected one V13 lineup board, got {board.count()}")
            cards = board.locator("article.krush13-card")
            if cards.count() != len(expected):
                raise BrowserQAFailure(
                    f"V13 card count mismatch: ui={cards.count()} api={len(expected)}"
                )

            rendered: list[dict] = []
            rendered_ranks: list[int] = []
            for index, wanted in enumerate(expected):
                card = cards.nth(index)
                text = card.inner_text()
                match = ATHLETE_RE.search(text)
                if not match:
                    raise BrowserQAFailure(f"V13 card {index} lost exact ESPN athlete identity")
                actual_athlete = match.group(1)
                if actual_athlete != wanted["official_athlete_id"]:
                    raise BrowserQAFailure(
                        "V13 favorable-first order mismatch at index "
                        f"{index}: ui={actual_athlete} expected={wanted['official_athlete_id']}"
                    )
                actual_tier = (card.get_attribute("data-matchup-tier") or "").strip().upper()
                if actual_tier != wanted["tier"]:
                    raise BrowserQAFailure(
                        f"V13 tier mismatch for ESPN athlete {actual_athlete}: "
                        f"ui={actual_tier} expected={wanted['tier']}"
                    )
                expected_line = _line_text(wanted.get("line"))
                if expected_line not in text:
                    raise BrowserQAFailure(
                        f"V13 card for ESPN athlete {actual_athlete} missing live line {expected_line}"
                    )
                if "projection influence 0.0%" not in text.lower():
                    raise BrowserQAFailure(
                        f"V13 card for ESPN athlete {actual_athlete} lost 0.0% influence marker"
                    )
                rendered_ranks.append(tiers_page.TIER_ORDER[actual_tier])
                rendered.append({**wanted, "ui_tier": actual_tier})

            if rendered_ranks != sorted(rendered_ranks):
                raise BrowserQAFailure("V13 cards are not sorted FAVORABLE -> MEDIUM -> TOUGH")
            if "FAVORABLE → MEDIUM → TOUGH" not in body:
                raise BrowserQAFailure("V13 page lost visible favorable-first ordering legend")

            screenshot = artifacts / "rushing_v13_matchup_tiers_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            tier_counts = {
                tier: sum(1 for row in rendered if row["ui_tier"] == tier)
                for tier in ("FAVORABLE", "MEDIUM", "TOUGH")
            }
            result = {
                "status": "GREEN",
                "route": "NFL -> Rushing Yards",
                "official_event_id": event_id,
                "live_api_prop_count": len(expected),
                "rendered_card_count": cards.count(),
                "tier_counts": tier_counts,
                "favorable_first": True,
                "rendered": rendered,
                "sportsbook_projection_influence": 0.0,
                "betting_grade_enabled": False,
                "projection_math_changed": False,
                "root_http": health["root_http"],
                "health_http": health["health_http"],
                "frame_scan_count": len(scan),
                "screenshot": str(screenshot),
            }
            (artifacts / "rushing_v13_matchup_tiers_metrics.json").write_text(
                json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
            )
            print("NFL_RUSHING_V13_MATCHUP_TIERS_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        except Exception:
            try:
                page.screenshot(path=str(artifacts / "rushing_v13_matchup_tiers_failure.png"), full_page=True)
            except Exception:
                pass
            raise
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--artifact-dir", default="artifacts/rushing-v13-matchup-tiers")
    parser.add_argument("--event-id", default=DEFAULT_EVENT_ID)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_witness(base_url=args.base_url, artifact_dir=args.artifact_dir, event_id=args.event_id)
