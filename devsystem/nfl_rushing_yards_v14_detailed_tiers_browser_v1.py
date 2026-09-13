"""Real Streamlit browser witness for V14 detailed Rushing player tiers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
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
import nfl_rushing_yards_projection_v1 as projection
import nfl_rushing_yards_hub_v13 as tiers_page

DEFAULT_BASE_URL = "http://127.0.0.1:8509"
DEFAULT_EVENT_ID = "401872925"
FAST_QUERY = "?ks_nfl_sport=NFL&ks_nfl_market=Rushing%20Yards"
V14_MARKER = "matchup classification only"
READY_MARKER = "Monster Performance Diagnosis"


def _expected_rows(context: dict) -> list[dict]:
    result = projection.build_event_projections(context)
    if result.get("ready") is not True:
        raise BrowserQAFailure("Certified Rushing projections unavailable for V14 witness")
    teams = tiers_page.prior._team_map(context)
    expected: list[dict] = []
    for index, row in enumerate(result.get("projections") or []):
        if not isinstance(row, dict):
            continue
        athlete_id = str(row.get("official_athlete_id") or "").strip()
        team_id = str(row.get("official_team_id") or "").strip()
        opponent_id = str(row.get("opponent_official_team_id") or "").strip()
        if not athlete_id.isdigit() or not team_id.isdigit() or not opponent_id.isdigit():
            raise BrowserQAFailure("Projection row lost exact ESPN identity")
        team = teams.get(team_id)
        opponent = teams.get(opponent_id)
        if not isinstance(team, dict) or not isinstance(opponent, dict):
            raise BrowserQAFailure(f"Certified context missing team/opponent for {athlete_id}")
        grade = tiers_page._matchup_tier(team, opponent)
        expected.append(
            {
                "official_athlete_id": athlete_id,
                "official_team_id": team_id,
                "player_name": row.get("player_name"),
                "tier": grade["tier"],
                "score": grade["score"],
                "original_index": index,
            }
        )
    expected.sort(
        key=lambda item: (
            tiers_page.TIER_ORDER.get(item["tier"], 1),
            item["original_index"],
        )
    )
    return expected


def run_witness(*, base_url: str, artifact_dir: str | Path, event_id: str) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    context = context_api.fetch_event_context(event_id)
    if context.get("ready") is not True:
        raise BrowserQAFailure(
            "Certified Rushing context unavailable for V14 witness: "
            + str(context.get("reason") or "unknown reason")
        )
    expected = _expected_rows(context)
    if not expected:
        raise BrowserQAFailure("V14 witness has no certified projection rows")

    health = _wait_for_health(base_url)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 2400})
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
                raise BrowserQAFailure(f"V14 page contains runtime error marker: {forbidden}")
            if f"official ESPN event {event_id}" not in body:
                raise BrowserQAFailure(f"V14 page did not select exact ESPN event {event_id}")
            for raw_marker in ('<section class="krush14-player"', '<div class="krush14-ribbon"'):
                if raw_marker in body:
                    raise BrowserQAFailure(f"V14 page leaked literal HTML: {raw_marker}")

            stacks = frame.locator("section.krush14-player")
            if stacks.count() != len(expected):
                raise BrowserQAFailure(
                    f"V14 detailed stack count mismatch: ui={stacks.count()} expected={len(expected)}"
                )

            rendered: list[dict] = []
            rendered_ranks: list[int] = []
            for index, wanted in enumerate(expected):
                stack = stacks.nth(index)
                actual_athlete = (stack.get_attribute("data-athlete-id") or "").strip()
                actual_tier = (stack.get_attribute("data-matchup-tier") or "").strip().upper()
                if actual_athlete != wanted["official_athlete_id"]:
                    raise BrowserQAFailure(
                        f"V14 detailed order mismatch at {index}: ui={actual_athlete} expected={wanted['official_athlete_id']}"
                    )
                if actual_tier != wanted["tier"]:
                    raise BrowserQAFailure(
                        f"V14 detailed tier mismatch for {actual_athlete}: ui={actual_tier} expected={wanted['tier']}"
                    )
                ribbon = stack.locator("div.krush14-ribbon")
                if ribbon.count() != 1 or actual_tier not in ribbon.first.inner_text():
                    raise BrowserQAFailure(f"V14 detailed stack {actual_athlete} lost visible tier ribbon")
                if stack.locator("article.krush4-card").count() != 1:
                    raise BrowserQAFailure(f"V14 detailed stack {actual_athlete} lost compact player card")
                if stack.locator('section[aria-label="Projection supports and concerns"]').count() != 1:
                    raise BrowserQAFailure(f"V14 detailed stack {actual_athlete} lost final support/concern panel")
                rendered_ranks.append(tiers_page.TIER_ORDER[actual_tier])
                rendered.append({**wanted, "ui_tier": actual_tier})

            if rendered_ranks != sorted(rendered_ranks):
                raise BrowserQAFailure("V14 detailed stacks are not sorted FAVORABLE -> MEDIUM -> TOUGH")
            if "sportsbook projection influence 0.0%" not in body.lower():
                raise BrowserQAFailure("V14 page lost 0.0% sportsbook projection influence marker")

            screenshot = artifacts / "rushing_v14_detailed_tiers_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "route": "NFL -> Rushing Yards",
                "official_event_id": event_id,
                "projection_row_count": len(expected),
                "rendered_detailed_stack_count": stacks.count(),
                "tier_counts": {
                    tier: sum(1 for row in rendered if row["ui_tier"] == tier)
                    for tier in ("FAVORABLE", "MEDIUM", "TOUGH")
                },
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
            (artifacts / "rushing_v14_detailed_tiers_metrics.json").write_text(
                json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
            )
            print("NFL_RUSHING_V14_DETAILED_TIERS_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        except Exception:
            try:
                page.screenshot(path=str(artifacts / "rushing_v14_detailed_tiers_failure.png"), full_page=True)
            except Exception:
                pass
            raise
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--artifact-dir", default="artifacts/rushing-v14-detailed-tiers")
    parser.add_argument("--event-id", default=DEFAULT_EVENT_ID)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_witness(base_url=args.base_url, artifact_dir=args.artifact_dir, event_id=args.event_id)
