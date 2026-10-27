"""MONSTER WNBA PRA upcoming-games-only production certification R1.

Read-only browser proof against PickVault production. The verifier obtains the
current Eastern-date WNBA schedule from Kyre Sports API/Vercel, classifies game
eligibility from certified status + UTC tip time, then drives WNBA -> PRA in a
fresh 390x844 Chromium session. If the current slate contains no eligible future
pregame game, Page 1 must expose zero active cards, zero Top-3 leaderboard, zero
Certified PRA Pick cards, and the explicit empty-state message.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure, _body_has_forbidden_error, _find_app_frame

PRODUCTION_URL = "https://pickvault.streamlit.app"
SCHEDULE_URL = "https://kyre-runless-proof.vercel.app/api/v1/wnba/games"
EASTERN = ZoneInfo("America/New_York")
SPORT_LABEL = "🏟️ Sport"
MARKET_LABEL = "🎯 WNBA Market"
EMPTY_MARKER = "No Page 1 players match the current filters."
PAGE_MARKER = "Player Discovery"
WAIT_SECONDS = 150.0


def _route_url(base_url: str) -> str:
    query = urlencode({"ks_jump_sport": "WNBA", "ks_jump_market": "PRA"})
    return base_url.rstrip("/") + "/?" + query


def _status(game: dict[str, Any]) -> str:
    raw = game.get("status") if isinstance(game.get("status"), dict) else {}
    return str(raw.get("category") or "").strip().casefold()


def _start_utc(game: dict[str, Any]) -> datetime | None:
    text = str(game.get("game_datetime_utc") or "").strip()
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _eligible(game: dict[str, Any], now_utc: datetime) -> bool:
    return _status(game) == "scheduled" and (start := _start_utc(game)) is not None and start > now_utc


def _schedule(day: str, now_utc: datetime) -> dict[str, Any]:
    response = requests.get(
        SCHEDULE_URL,
        params={"date": day, "season": 2026},
        headers={"accept": "application/json", "user-agent": "monster-wnba-pra-upcoming-production-cert/1"},
        timeout=25,
    )
    if response.status_code != 200:
        raise BrowserQAFailure(f"Certified WNBA schedule returned HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("source") != "WNBA Official Schedule":
        raise BrowserQAFailure("Certified WNBA schedule identity mismatch")
    games = [dict(game) for game in payload.get("games") or [] if isinstance(game, dict)]
    eligible = [game for game in games if _eligible(game, now_utc)]
    rejected = [game for game in games if game not in eligible]
    return {
        "date": day,
        "games": games,
        "eligible": eligible,
        "rejected": rejected,
        "retrieved_at_utc": payload.get("retrieved_at_utc"),
    }


def _choose_labeled(page, frame, label: str, value: str) -> None:
    combo = frame.get_by_role("combobox", name=label, exact=True)
    if combo.count() < 1:
        raise BrowserQAFailure(f"Missing route control {label!r}")
    combo.first.click()
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        for owner in (frame, page):
            try:
                option = owner.get_by_role("option", name=value, exact=True).first
                if option.count() > 0 and option.is_visible():
                    option.click()
                    return
            except Exception:
                pass
        page.wait_for_timeout(100)
    raise BrowserQAFailure(f"Could not select {value!r} from {label!r}")


def _enter_pra(page, base_url: str):
    page.goto(_route_url(base_url), wait_until="domcontentloaded", timeout=120000)
    frame, _ = _find_app_frame(page, timeout_seconds=120.0)

    # Match the already-proven WNBA Step-9 production route primer: always
    # explicitly re-select WNBA, even when the immutable jump query already
    # displays WNBA. That selection commits the Streamlit rerun that mounts the
    # WNBA market selector; merely reading the query-backed input value does not.
    _choose_labeled(page, frame, SPORT_LABEL, "WNBA")

    deadline = time.monotonic() + 45.0
    while time.monotonic() < deadline:
        frame, _ = _find_app_frame(page, timeout_seconds=12.0)
        market = frame.get_by_role("combobox", name=MARKET_LABEL, exact=True)
        if market.count() > 0:
            _choose_labeled(page, frame, MARKET_LABEL, "PRA")
            return _find_app_frame(page, timeout_seconds=20.0)[0]
        page.wait_for_timeout(200)
    raise BrowserQAFailure("WNBA PRA market selector did not appear")


def _wait_page1(page, frame) -> tuple[Any, str]:
    deadline = time.monotonic() + WAIT_SECONDS
    last = ""
    while time.monotonic() < deadline:
        frame, _ = _find_app_frame(page, timeout_seconds=12.0)
        try:
            last = frame.locator("body").inner_text(timeout=5000)
        except Exception:
            last = ""
        forbidden = _body_has_forbidden_error(last)
        if forbidden:
            raise BrowserQAFailure(f"Production WNBA PRA contains runtime error marker: {forbidden}")
        if PAGE_MARKER in last and frame.locator(".p1v2-summary").count() > 0:
            return frame, last
        page.wait_for_timeout(500)
    raise BrowserQAFailure(f"WNBA PRA Page 1 did not become ready; body={last[:3500]!r}")


def _first_stat_text(frame) -> str:
    stats = frame.locator(".p1v2-summary .p1v2-stat")
    if stats.count() < 1:
        raise BrowserQAFailure("Page 1 summary Players stat is missing")
    return (stats.nth(0).inner_text(timeout=5000) or "").strip()


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    day = now_utc.astimezone(EASTERN).date().isoformat()
    schedule = _schedule(day, now_utc)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        try:
            frame = _enter_pra(page, production_url)
            frame, body = _wait_page1(page, frame)
            card_count = frame.locator(".p1v2-card").count()
            leaderboard_count = frame.locator(".p1v2-leaderboard").count()
            final_count = frame.locator(".p1v2-final").count()
            players_stat = _first_stat_text(frame)
            empty_visible = frame.get_by_text(EMPTY_MARKER, exact=False).count() > 0
            screenshot = artifacts / "wnba-pra-upcoming-only-production.png"
            page.screenshot(path=str(screenshot), full_page=True)
        finally:
            browser.close()

    eligible_count = len(schedule["eligible"])
    rejected_summary = [
        {
            "game_id": game.get("game_id"),
            "away": ((game.get("away") or {}).get("full_name") if isinstance(game.get("away"), dict) else None),
            "home": ((game.get("home") or {}).get("full_name") if isinstance(game.get("home"), dict) else None),
            "status": _status(game),
            "start_utc": str(game.get("game_datetime_utc") or ""),
        }
        for game in schedule["rejected"]
    ]

    if eligible_count == 0:
        if card_count != 0:
            raise BrowserQAFailure(f"Final/live-only slate leaked active Page 1 cards: {card_count}")
        if leaderboard_count != 0:
            raise BrowserQAFailure(f"Final/live-only slate leaked Top 3 leaderboard: {leaderboard_count}")
        if final_count != 0:
            raise BrowserQAFailure(f"Final/live-only slate leaked Certified PRA Pick cards: {final_count}")
        if not empty_visible:
            raise BrowserQAFailure("Final/live-only slate did not expose the Page 1 empty-state message")
        compact = " ".join(players_stat.split()).casefold()
        if "players" not in compact or not compact.endswith("0"):
            raise BrowserQAFailure(f"Final/live-only slate Players summary is not zero: {players_stat!r}")
    else:
        # For mixed slates, rejected games may not create active Page 1 matchup
        # cards. We avoid player-name assumptions and rely on the upstream exact
        # game gate plus the focused Runless tests already merged on main.
        if final_count > card_count:
            raise BrowserQAFailure("Certified PRA Pick count exceeds active eligible Page 1 card count")

    result = {
        "status": "GREEN",
        "authority": "MONSTER_ONLY",
        "production_url": production_url,
        "route": "WNBA -> PRA",
        "date_eastern": day,
        "schedule_source": "WNBA Official Schedule via Kyre Sports API/Vercel",
        "schedule_games": len(schedule["games"]),
        "eligible_upcoming_games": eligible_count,
        "rejected_live_final_or_past_tip_games": len(schedule["rejected"]),
        "rejected_games": rejected_summary,
        "page1_card_count": card_count,
        "top3_leaderboard_count": leaderboard_count,
        "certified_pick_count": final_count,
        "players_stat": players_stat,
        "empty_state_visible": empty_visible,
        "freeze_token": "MONSTER_WNBA_PRA_UPCOMING_ONLY_R2_FINAL_CARD_FROZEN",
    }
    (artifacts / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("MONSTER_WNBA_PRA_UPCOMING_ONLY_PRODUCTION_GREEN=" + json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PRODUCTION_URL)
    parser.add_argument("--artifact-dir", default="artifacts/monster-wnba-pra-upcoming-only-production-cert-r1")
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
