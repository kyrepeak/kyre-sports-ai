"""MONSTER WNBA PRA future-pregame-only production certification R4.

Read-only Step 2G proof. Live, final, started, and historical games are never
selected or used as proof targets. Discover only future scheduled WNBA dates via
Kyre Sports API/Vercel, navigate PickVault through the current Universal Runtime
V5 Streamlit pill controls, then certify one real future WNBA -> PRA slate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
from typing import Any
from zoneinfo import ZoneInfo

import requests
from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure, _find_app_frame
from devsystem import wnba_nav_v2_step7_public_freeze as nav
from devsystem import wnba_pra_speed_v3_step9_final_cert as speed9

PRODUCTION_URL = "https://pickvault.streamlit.app"
SCHEDULE_URL = "https://kyre-runless-proof.vercel.app/api/v1/wnba/games"
EASTERN = ZoneInfo("America/New_York")
SEARCH_DAYS = 31
REQUEST_TIMEOUT_SECONDS = 20.0
NAV_TIMEOUT_SECONDS = 45.0
NAV_SHELL = ".st-key-ks_universal_nav_shell"
PILLS = 'div[data-testid="stPills"]'
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


def _future_pregame_dates() -> tuple[str, ...]:
    now_utc = datetime.now(timezone.utc)
    today = now_utc.astimezone(EASTERN).date()
    session = requests.Session()
    dates: list[str] = []
    errors: list[str] = []
    for offset in range(SEARCH_DAYS + 1):
        day = today + timedelta(days=offset)
        text = day.isoformat()
        try:
            response = session.get(
                SCHEDULE_URL,
                params={"date": text, "season": 2026},
                headers={"accept": "application/json", "user-agent": "monster-wnba-future-only-cert/4"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                errors.append(f"{text}:HTTP{response.status_code}")
                continue
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("source") != "WNBA Official Schedule":
                errors.append(f"{text}:IDENTITY")
                continue
            games = payload.get("games")
            if not isinstance(games, list):
                continue
            for game in games:
                if not isinstance(game, dict) or _status(game) != "scheduled":
                    continue
                start = _start_utc(game)
                if start is not None and start > now_utc:
                    dates.append(text)
                    break
        except Exception as exc:
            errors.append(f"{text}:{type(exc).__name__}")
    if not dates:
        raise BrowserQAFailure(
            f"No future scheduled WNBA game found within {SEARCH_DAYS} days; errors={errors[:5]}"
        )
    return tuple(dates)


def _pill_values(frame, group_index: int) -> list[str]:
    groups = frame.locator(NAV_SHELL).locator(PILLS)
    if groups.count() <= group_index:
        return []
    buttons = groups.nth(group_index).locator("button")
    out: list[str] = []
    for index in range(buttons.count()):
        try:
            text = (buttons.nth(index).inner_text(timeout=3000) or "").strip()
        except Exception:
            text = ""
        if text:
            out.append(text)
    return out


def _click_pill(page, group_index: int, label: str):
    deadline = time.monotonic() + NAV_TIMEOUT_SECONDS
    seen: list[str] = []
    while time.monotonic() < deadline:
        frame, _ = _find_app_frame(page, timeout_seconds=12.0)
        groups = frame.locator(NAV_SHELL).locator(PILLS)
        if groups.count() > group_index:
            buttons = groups.nth(group_index).locator("button")
            seen = []
            for index in range(buttons.count()):
                button = buttons.nth(index)
                try:
                    text = (button.inner_text(timeout=3000) or "").strip()
                except Exception:
                    text = ""
                if text:
                    seen.append(text)
                if text == label:
                    button.click()
                    page.wait_for_timeout(700)
                    return _find_app_frame(page, timeout_seconds=20.0)[0]
        page.wait_for_timeout(150)
    raise BrowserQAFailure(f"Navigation pill {label!r} missing; saw={seen!r}")


def _route_wnba_pra(page, production_url: str):
    page.goto(production_url, wait_until="domcontentloaded", timeout=90000)
    _find_app_frame(page, timeout_seconds=90.0)
    frame = _click_pill(page, 0, "WNBA")
    deadline = time.monotonic() + NAV_TIMEOUT_SECONDS
    markets: list[str] = []
    while time.monotonic() < deadline:
        frame, _ = _find_app_frame(page, timeout_seconds=12.0)
        markets = _pill_values(frame, 1)
        if "PRA" in markets:
            break
        page.wait_for_timeout(150)
    else:
        raise BrowserQAFailure(f"WNBA market pills never mounted; saw={markets!r}")
    return _click_pill(page, 1, "PRA")


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    dates = _future_pregame_dates()
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    selected = ""
    game_count = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        try:
            frame = _route_wnba_pra(page, production_url)
            for target in dates:
                try:
                    frame = speed9._set_future_slate_date_segmented(page, frame, target)
                except Exception:
                    continue
                game_count = int(nav._game_button(frame).count())
                if game_count > 0:
                    selected = target
                    break
            if not selected:
                raise BrowserQAFailure("PickVault could not render a discovered future pregame WNBA slate")
            body = nav._body(frame)
            if "wnba" not in body.casefold() or "pra" not in body.casefold():
                raise BrowserQAFailure("Future-only cert left WNBA/PRA route")
            page.screenshot(path=str(artifacts / "wnba-pra-future-pregame-production.png"), full_page=True)
        finally:
            context.close()
            browser.close()

    result = {
        "status": "GREEN",
        "authority": "MONSTER_ONLY",
        "production_url": production_url,
        "route": "WNBA -> PRA",
        "navigation_contract": "Universal Runtime V5 Streamlit pills",
        "schedule_source": "WNBA Official Schedule via Kyre Sports API/Vercel",
        "future_pregame_dates": list(dates),
        "selected_future_date": selected,
        "public_future_game_count": game_count,
        "live_games_used_as_target": False,
        "final_games_used_as_target": False,
        "started_games_used_as_target": False,
        "historical_games_used_as_target": False,
        "future_pregame_only": True,
        "api2_state_used": False,
        "freeze_token": FREEZE_TOKEN,
    }
    (artifacts / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("MONSTER_WNBA_PRA_FUTURE_PREGAME_PRODUCTION_GREEN=" + json.dumps(result, sort_keys=True))
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
