"""MONSTER WNBA PRA upcoming-games-only production certification R2.

Read-only Step 2G browser proof. It never selects or analyzes a live, final,
started, or historical game. The verifier reads only official schedule state to
establish whether the current Eastern-date slate has any future pregame game,
then opens PickVault WNBA -> PRA through the repository's already-proven public
navigation helper. When no future pregame game exists, the production surface
must contain zero active Page-1 analytical cards, zero Top-3 leaderboard, and
zero Certified PRA Pick cards.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any
from zoneinfo import ZoneInfo

import requests
from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure, _find_app_frame
from devsystem.wnba_pra_step3_public_freeze_v1 import (
    OFF_DAY_MARKER,
    _body,
    _route_to_wnba_pra,
    _wnba_surface,
)

PRODUCTION_URL = "https://pickvault.streamlit.app"
SCHEDULE_URL = "https://kyre-runless-proof.vercel.app/api/v1/wnba/games"
EASTERN = ZoneInfo("America/New_York")
REQUEST_TIMEOUT_SECONDS = 25.0
EMPTY_MARKER = "No Page 1 players match the current filters."
FREEZE_TOKEN = "MONSTER_WNBA_PRA_UPCOMING_ONLY_R2_FINAL_CARD_FROZEN"


def _status(game: dict[str, Any]) -> str:
    raw = game.get("status") if isinstance(game.get("status"), dict) else {}
    return str(raw.get("category") or "").strip().casefold()


def _start_utc(game: dict[str, Any]) -> datetime | None:
    text = str(game.get("game_datetime_utc") or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _current_schedule(now_utc: datetime) -> dict[str, Any]:
    day = now_utc.astimezone(EASTERN).date().isoformat()
    response = requests.get(
        SCHEDULE_URL,
        params={"date": day, "season": 2026},
        headers={
            "accept": "application/json",
            "user-agent": "monster-wnba-pra-current-slate-exclusion-cert/2",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise BrowserQAFailure(f"Certified WNBA schedule returned HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("source") != "WNBA Official Schedule":
        raise BrowserQAFailure("Certified WNBA schedule identity mismatch")
    games = [dict(item) for item in payload.get("games") or [] if isinstance(item, dict)]
    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for game in games:
        start = _start_utc(game)
        if _status(game) == "scheduled" and start is not None and start > now_utc:
            eligible.append(game)
        else:
            rejected.append(game)
    return {
        "date": day,
        "games": games,
        "eligible": eligible,
        "rejected": rejected,
        "retrieved_at_utc": payload.get("retrieved_at_utc"),
    }


def _wait_settled(page, frame) -> tuple[Any, str, str]:
    deadline = time.monotonic() + 90.0
    last_surface = ""
    stable = 0
    body = ""
    surface = ""
    while time.monotonic() < deadline:
        frame, _ = _find_app_frame(page, timeout_seconds=15.0)
        try:
            body = _body(frame)
        except Exception:
            body = ""
        surface = _wnba_surface(body)
        has_route = "WNBA PRA" in surface or "KYRE SPORTS AI • WNBA" in surface
        has_terminal_state = (
            OFF_DAY_MARKER in surface
            or EMPTY_MARKER in surface
            or frame.locator(".p1v2-summary").count() > 0
        )
        if has_route and has_terminal_state:
            if surface == last_surface:
                stable += 1
            else:
                last_surface = surface
                stable = 1
            if stable >= 2:
                return frame, body, surface
        else:
            stable = 0
            last_surface = surface
        page.wait_for_timeout(750)
    raise BrowserQAFailure(
        "WNBA PRA production did not reach a settled terminal surface; "
        f"body={body[:5000]!r}"
    )


def _rejected_summary(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "game_id": game.get("game_id"),
            "away": ((game.get("away") or {}).get("full_name") if isinstance(game.get("away"), dict) else None),
            "home": ((game.get("home") or {}).get("full_name") if isinstance(game.get("home"), dict) else None),
            "status": _status(game),
            "start_utc": str(game.get("game_datetime_utc") or ""),
        }
        for game in games
    ]


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    schedule = _current_schedule(now_utc)

    # This certificate is specifically for the no-future-pregame state. If a new
    # future WNBA game appears, fail closed rather than selecting it automatically.
    if schedule["eligible"]:
        raise BrowserQAFailure(
            "Current WNBA slate now contains a future pregame game; this exclusion "
            "certificate intentionally refuses to select or analyze it automatically."
        )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        try:
            page.goto(production_url, wait_until="domcontentloaded", timeout=90000)
            frame, _ = _route_to_wnba_pra(page)
            frame, body, surface = _wait_settled(page, frame)

            active_cards = int(frame.locator(".p1v2-card").count())
            top3 = int(frame.locator(".p1v2-leaderboard").count())
            certified = int(frame.locator(".p1v2-final").count())
            game_buttons = int(frame.locator("button").filter(has_text="@").count())
            empty_state = EMPTY_MARKER in surface or OFF_DAY_MARKER in surface

            screenshot = artifacts / "wnba-pra-current-slate-exclusion-production.png"
            page.screenshot(path=str(screenshot), full_page=True)
        finally:
            context.close()
            browser.close()

    if active_cards != 0:
        raise BrowserQAFailure(f"Final/started-only slate leaked active Page 1 cards: {active_cards}")
    if top3 != 0:
        raise BrowserQAFailure(f"Final/started-only slate leaked Top 3 leaderboard: {top3}")
    if certified != 0:
        raise BrowserQAFailure(f"Final/started-only slate leaked Certified PRA Pick cards: {certified}")
    if game_buttons != 0:
        raise BrowserQAFailure(f"Final/started-only slate leaked active game buttons: {game_buttons}")
    if not empty_state:
        raise BrowserQAFailure(
            "Final/started-only slate did not expose an accepted no-active-game empty state"
        )

    result = {
        "status": "GREEN",
        "authority": "MONSTER_ONLY",
        "production_url": production_url,
        "route": "WNBA -> PRA",
        "date_eastern": schedule["date"],
        "schedule_source": "WNBA Official Schedule via Kyre Sports API/Vercel",
        "schedule_games": len(schedule["games"]),
        "eligible_future_pregame_games": 0,
        "rejected_started_live_final_or_past_tip_games": len(schedule["rejected"]),
        "rejected_games": _rejected_summary(schedule["rejected"]),
        "page1_active_card_count": active_cards,
        "top3_leaderboard_count": top3,
        "certified_pick_count": certified,
        "active_game_button_count": game_buttons,
        "accepted_empty_state_visible": empty_state,
        "selected_game": False,
        "live_games_used_as_target": False,
        "final_games_used_as_target": False,
        "historical_games_used_as_target": False,
        "api2_state_used": False,
        "freeze_token": FREEZE_TOKEN,
    }
    (artifacts / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("MONSTER_WNBA_PRA_CURRENT_SLATE_EXCLUSION_GREEN=" + json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PRODUCTION_URL)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/monster-wnba-pra-upcoming-only-production-cert-r1",
    )
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
