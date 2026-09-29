"""WNBA Navigation V2 Step 7 — public production speed proof + final freeze.

Proof-only browser certification. It changes no runtime product state.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo

import requests
from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure, _choose, _find_app_frame

PUBLIC_HOST = "https://pickvault.streamlit.app"
API_GAMES = "https://kyre-sports-api.onrender.com/api/v1/wnba/games"
VIEWPORT = {"width": 1440, "height": 1200}
SLATE_READY_BUDGET_SECONDS = 12.0
GAME_READY_BUDGET_SECONDS = 24.0
PLAYER_READY_BUDGET_SECONDS = 24.0
BACK_READY_BUDGET_SECONDS = 12.0


def _body(frame) -> str:
    return frame.locator("body").inner_text(timeout=5000)


def _step6_marker(frame, page_name: str):
    return frame.locator(
        f'[data-wnba-nav-v2-step6="responsive-integration"][data-wnba-nav-page="{page_name}"]'
    )


def _step5_marker(frame, page_name: str):
    return frame.locator(
        f'[data-wnba-nav-v2-step5="performance"][data-wnba-nav-page="{page_name}"]'
    )


def _wait_page(page, page_name: str, *, timeout_seconds: float) -> tuple[object, float]:
    started = time.monotonic()
    deadline = started + timeout_seconds
    last = ""
    while time.monotonic() < deadline:
        frame, _ = _find_app_frame(page, timeout_seconds=min(15.0, max(2.0, deadline-time.monotonic())))
        try:
            if _step6_marker(frame, page_name).count() and _step5_marker(frame, page_name).count():
                body = _body(frame)
                if page_name == "slate" and "WNBA Slate" in body:
                    return frame, time.monotonic() - started
                if page_name == "game" and "WNBA Game Center" in body:
                    buttons = frame.get_by_role("button", name=re.compile(r"^Open .+ PRA →$"))
                    if buttons.count() > 0:
                        return frame, time.monotonic() - started
                if page_name == "player" and "WNBA PRA Intelligence" in body:
                    return frame, time.monotonic() - started
            last = _body(frame)[:5000]
        except Exception:
            pass
        page.wait_for_timeout(350)
    raise BrowserQAFailure(f"Step-7 {page_name} page did not become ready. body={last!r}")


def _overflow(frame) -> tuple[int, int]:
    return tuple(frame.locator("html").evaluate(
        "el => [Math.ceil(el.scrollWidth), Math.ceil(el.clientWidth)]"
    ))


def _assert_no_overflow(frame, label: str) -> None:
    scroll, client = _overflow(frame)
    if scroll > client + 1:
        raise BrowserQAFailure(f"{label} horizontal overflow: scroll={scroll} client={client}")
    print(f"WNBA_NAV_STEP7_{label.upper()}_ZERO_OVERFLOW_GREEN")


def _route_to_wnba_pra(page) -> tuple[object, float]:
    frame, _ = _find_app_frame(page, timeout_seconds=120.0)
    _choose(page, frame, 0, "WNBA")

    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        frame, _ = _find_app_frame(page, timeout_seconds=12.0)
        if frame.get_by_role("combobox").count() >= 2:
            break
        page.wait_for_timeout(300)
    else:
        raise BrowserQAFailure("WNBA market selector did not appear.")

    _choose(page, frame, 1, "PRA")
    frame, ready = _wait_page(page, "slate", timeout_seconds=SLATE_READY_BUDGET_SECONDS)
    if ready > SLATE_READY_BUDGET_SECONDS:
        raise BrowserQAFailure(f"slate ready budget exceeded: {ready:.3f}s")
    print(f"WNBA_NAV_STEP7_PUBLIC_SLATE_READY_SECONDS={ready:.3f}")
    return frame, ready


def _game_button(frame):
    return frame.get_by_role("button", name="Open Game Center →", exact=True)


def _find_game_date() -> str:
    today = datetime.now(ZoneInfo("America/New_York")).date()
    offsets = [0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6, -7, 7, -10, 10, -14, 14]
    session = requests.Session()
    errors = []
    for offset in offsets:
        day = today + timedelta(days=offset)
        try:
            response = session.get(
                API_GAMES,
                params={"date": day.isoformat(), "season": 2026},
                headers={"accept": "application/json", "user-agent": "wnba-nav-v2-step7-final-freeze/1"},
                timeout=8,
            )
            if response.status_code != 200:
                errors.append(f"{day}:HTTP{response.status_code}")
                continue
            payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("games"), list) and payload["games"]:
                print(f"WNBA_NAV_STEP7_GAME_DATE={day.isoformat()}")
                return day.isoformat()
        except Exception as exc:
            errors.append(f"{day}:{type(exc).__name__}")
    raise BrowserQAFailure("No live WNBA game date found near today; " + ",".join(errors[-8:]))


def _set_date_with_game(page, frame, target: str) -> object:
    date_input = frame.locator('[data-testid="stDateInput"] input').first
    if date_input.count() < 1:
        date_input = frame.get_by_label("📅 Slate date", exact=True)
    if date_input.count() < 1:
        raise BrowserQAFailure("WNBA Slate date input missing.")

    day = datetime.fromisoformat(target).date()
    attempts = [target, day.strftime("%m/%d/%Y"), day.strftime("%Y/%m/%d"), day.strftime("%m-%d-%Y")]
    errors = []
    for value in attempts:
        try:
            current = frame.locator('[data-testid="stDateInput"] input').first
            if current.count() < 1:
                current = frame.get_by_label("📅 Slate date", exact=True)
            current.fill(value)
            current.press("Enter")
            page.keyboard.press("Tab")
            deadline = time.monotonic() + 12.0
            while time.monotonic() < deadline:
                frame, _ = _find_app_frame(page, timeout_seconds=8.0)
                if _game_button(frame).count() > 0:
                    print(f"WNBA_NAV_STEP7_SLATE_DATE_GREEN={target}")
                    return frame
                page.wait_for_timeout(350)
        except Exception as exc:
            errors.append(f"{value}:{type(exc).__name__}")
    raise BrowserQAFailure(f"Could not activate WNBA game date {target}; {errors}")


def _ensure_game_on_slate(page, frame) -> object:
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if _game_button(frame).count() > 0:
            return frame
        if "No WNBA games are scheduled for this date." in _body(frame):
            break
        page.wait_for_timeout(350)
        frame, _ = _find_app_frame(page, timeout_seconds=8.0)
    return _set_date_with_game(page, frame, _find_game_date())


def run(*, production_url: str, artifact_dir: str | Path) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    result = {
        "project": "WNBA Navigation V2",
        "step": "7/7",
        "production_url": production_url,
        "status": "BLOCKED",
        "speed_budgets_seconds": {
            "slate": SLATE_READY_BUDGET_SECONDS,
            "game": GAME_READY_BUDGET_SECONDS,
            "player": PLAYER_READY_BUDGET_SECONDS,
            "back": BACK_READY_BUDGET_SECONDS,
        },
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        try:
            page.goto(production_url, wait_until="domcontentloaded", timeout=120000)
            frame, slate_seconds = _route_to_wnba_pra(page)
            frame = _ensure_game_on_slate(page, frame)
            _assert_no_overflow(frame, "slate")

            body = _body(frame)
            if "No player/model prefetch" not in body or "Detailed PRA edges stay asleep on this page" not in body:
                raise BrowserQAFailure("Slate lazy-load contract is not visible.")
            if frame.locator(".wn3-player").count() or frame.locator(".wn4-hero").count():
                raise BrowserQAFailure("Slate woke Game/Player heavy surfaces before selection.")
            print("WNBA_NAV_STEP7_SLATE_LAZY_LOADING_GREEN")

            game_button = _game_button(frame).first
            game_started = time.monotonic()
            game_button.click()
            frame, _ = _wait_page(page, "game", timeout_seconds=GAME_READY_BUDGET_SECONDS)
            game_seconds = time.monotonic() - game_started
            if game_seconds > GAME_READY_BUDGET_SECONDS:
                raise BrowserQAFailure(f"game ready budget exceeded: {game_seconds:.3f}s")
            _assert_no_overflow(frame, "game")
            print(f"WNBA_NAV_STEP7_PUBLIC_GAME_READY_SECONDS={game_seconds:.3f}")

            player_buttons = frame.get_by_role("button", name=re.compile(r"^Open .+ PRA →$"))
            if player_buttons.count() < 1:
                raise BrowserQAFailure("No player PRA drill-down button is available on Game Center.")
            player_started = time.monotonic()
            player_buttons.first.click()
            frame, _ = _wait_page(page, "player", timeout_seconds=PLAYER_READY_BUDGET_SECONDS)
            player_seconds = time.monotonic() - player_started
            if player_seconds > PLAYER_READY_BUDGET_SECONDS:
                raise BrowserQAFailure(f"player ready budget exceeded: {player_seconds:.3f}s")
            _assert_no_overflow(frame, "player")
            print(f"WNBA_NAV_STEP7_PUBLIC_PLAYER_READY_SECONDS={player_seconds:.3f}")

            player_body = _body(frame)
            required_player = (
                "Final Decision",
                "Recent Form",
                "Matchup + Pace",
                "Minutes, Role, Usage + Availability",
                "Same-Opponent H2H Context",
            )
            missing = [x for x in required_player if x not in player_body]
            if missing:
                raise BrowserQAFailure(f"Player Intelligence missing final frozen surfaces: {missing}")
            print("WNBA_NAV_STEP7_PLAYER_INTELLIGENCE_GREEN")

            back_game = frame.get_by_role("button", name="← Back to Game Center", exact=True)
            back_started = time.monotonic()
            back_game.click()
            frame, _ = _wait_page(page, "game", timeout_seconds=BACK_READY_BUDGET_SECONDS)
            back_game_seconds = time.monotonic() - back_started
            if back_game_seconds > BACK_READY_BUDGET_SECONDS:
                raise BrowserQAFailure(f"player->game back budget exceeded: {back_game_seconds:.3f}s")
            print(f"WNBA_NAV_STEP7_PUBLIC_PLAYER_BACK_SECONDS={back_game_seconds:.3f}")

            back_slate = frame.get_by_role("button", name="← Back to WNBA Slate", exact=True)
            back_started = time.monotonic()
            back_slate.click()
            frame, _ = _wait_page(page, "slate", timeout_seconds=BACK_READY_BUDGET_SECONDS)
            back_slate_seconds = time.monotonic() - back_started
            if back_slate_seconds > BACK_READY_BUDGET_SECONDS:
                raise BrowserQAFailure(f"game->slate back budget exceeded: {back_slate_seconds:.3f}s")
            print(f"WNBA_NAV_STEP7_PUBLIC_GAME_BACK_SECONDS={back_slate_seconds:.3f}")

            result.update({
                "status": "GREEN",
                "slate_ready_seconds": round(slate_seconds, 3),
                "game_ready_seconds": round(game_seconds, 3),
                "player_ready_seconds": round(player_seconds, 3),
                "player_back_seconds": round(back_game_seconds, 3),
                "game_back_seconds": round(back_slate_seconds, 3),
                "three_page_public_path_green": True,
                "lazy_loading_green": True,
                "zero_horizontal_overflow_green": True,
                "observed_at_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
            })
            page.screenshot(path=str(artifacts / "wnba_nav_v2_step7_final_green.png"), full_page=True)
            (artifacts / "wnba_nav_v2_step7_evidence.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print("WNBA_NAV_STEP7_PUBLIC_SPEED_GREEN")
            print("WNBA_NAV_STEP7_THREE_PAGE_PRODUCTION_GREEN")
            print("WNBA_NAV_STEP7_GREEN")
            print("WNBA_NAV_STEP7_FROZEN")
            return result
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument("--artifact-dir", default="artifacts/wnba-nav-v2-step7-final-freeze")
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
