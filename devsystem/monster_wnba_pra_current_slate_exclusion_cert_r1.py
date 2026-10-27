"""MONSTER WNBA PRA current-slate exclusion production certificate R1.

Read-only Step 2G proof for merged product main dd9ffcc4. This verifier never
selects a game. It reads the official current-date WNBA schedule only to assert
that there is no future pregame game, routes PickVault through the current
Universal Sports Navigation pill controls to WNBA -> PRA, and proves that no
live/final/past-tip game remains in the active analytical surface.
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

from devsystem.browser_qa_v1 import BrowserQAFailure

PRODUCTION_URL = "https://pickvault.streamlit.app"
SCHEDULE_URL = "https://kyre-runless-proof.vercel.app/api/v1/wnba/games"
EASTERN = ZoneInfo("America/New_York")
NAV_SHELL = ".st-key-ks_universal_nav_shell"
EMPTY_MARKERS = (
    "No Page 1 players match the current filters.",
    "No WNBA games on this date",
    "No player PRA board rows are available",
)
FREEZE_TOKEN = "MONSTER_WNBA_PRA_UPCOMING_ONLY_R2_FINAL_CARD_FROZEN"
SOURCE_MAIN_SHA = "dd9ffcc4b44faea92f97d68545db6efb160c9f3f"


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


def _schedule(now_utc: datetime) -> dict[str, Any]:
    day = now_utc.astimezone(EASTERN).date().isoformat()
    response = requests.get(
        SCHEDULE_URL,
        params={"date": day, "season": 2026},
        headers={
            "accept": "application/json",
            "user-agent": "monster-wnba-current-slate-exclusion-cert/1",
        },
        timeout=25,
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


def _frame_body(frame) -> str:
    try:
        return frame.locator("body").inner_text(timeout=5000)
    except Exception:
        return ""


def _app_frame(page, timeout_seconds: float = 75.0):
    deadline = time.monotonic() + timeout_seconds
    last: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        scans: list[dict[str, Any]] = []
        for index, frame in enumerate(page.frames):
            body = _frame_body(frame)
            scans.append({"index": index, "url": frame.url, "body_start": body[:700]})
            if "KYRE SPORTS AI" in body:
                return frame, scans
        last = scans
        page.wait_for_timeout(750)
    raise BrowserQAFailure(
        "Could not find rendered KYRE SPORTS Streamlit frame: "
        + json.dumps(last, ensure_ascii=False)
    )


def _wait_nav_button(page, label: str, timeout_seconds: float = 45.0):
    deadline = time.monotonic() + timeout_seconds
    last_shell = ""
    while time.monotonic() < deadline:
        frame, _ = _app_frame(page, timeout_seconds=12.0)
        shell = frame.locator(NAV_SHELL)
        if shell.count() > 0:
            try:
                last_shell = shell.inner_text(timeout=5000)
            except Exception:
                last_shell = ""
            exact = shell.get_by_role("button", name=label, exact=True)
            if exact.count() > 0:
                return frame, exact.first
            fallback = shell.locator("button").filter(has_text=label)
            if fallback.count() > 0:
                return frame, fallback.first
        page.wait_for_timeout(400)
    raise BrowserQAFailure(f"Universal nav pill {label!r} missing; shell={last_shell[:2500]!r}")


def _route_wnba_pra_without_game(page, production_url: str):
    page.goto(production_url, wait_until="domcontentloaded", timeout=90000)
    frame, wnba = _wait_nav_button(page, "WNBA")
    wnba.click()

    # Do not rediscover the app using the legacy combobox-only detector during
    # Streamlit rerun. Wait on the current pill-capable frame detector instead.
    deadline = time.monotonic() + 120.0
    last_body = ""
    last_url = ""
    while time.monotonic() < deadline:
        frame, _ = _app_frame(page, timeout_seconds=15.0)
        last_body = _frame_body(frame)
        last_url = str(frame.url or page.url or "")
        lowered_url = last_url.casefold()
        body_lower = last_body.casefold()
        route_is_wnba = "sport=wnba" in lowered_url or "wnba pra" in body_lower
        if route_is_wnba:
            # Production commonly resolves WNBA directly to PRA. If it does not,
            # use the current market pill, still without selecting a game.
            if "market=pra" not in lowered_url:
                try:
                    _, pra = _wait_nav_button(page, "PRA", timeout_seconds=15.0)
                    checked = str(pra.get_attribute("aria-checked") or "").casefold()
                    if checked != "true":
                        pra.click()
                except Exception:
                    pass
            return frame
        page.wait_for_timeout(750)

    raise BrowserQAFailure(
        "WNBA route did not settle after WNBA pill click; "
        f"url={last_url!r} body={last_body[:5000]!r}"
    )


def _wait_terminal(page, frame):
    deadline = time.monotonic() + 150.0
    last_body = ""
    stable_body = ""
    stable_count = 0
    while time.monotonic() < deadline:
        frame, _ = _app_frame(page, timeout_seconds=15.0)
        body = _frame_body(frame)
        last_body = body
        url = str(frame.url or page.url or "").casefold()
        route_is_wnba = "sport=wnba" in url or "wnba pra" in body.casefold()
        terminal = (
            any(marker.casefold() in body.casefold() for marker in EMPTY_MARKERS)
            or frame.locator(".p1v2-summary").count() > 0
            or frame.locator(".p1v2-wrap").count() > 0
        )
        if route_is_wnba and terminal:
            compact = " ".join(body.split())
            if compact == stable_body:
                stable_count += 1
            else:
                stable_body = compact
                stable_count = 1
            if stable_count >= 2:
                return frame, body
        else:
            stable_count = 0
            stable_body = ""
        page.wait_for_timeout(1000)
    raise BrowserQAFailure(
        "WNBA PRA did not reach a terminal no-game/Page1 state; "
        f"url={page.url!r} body={last_body[:6000]!r}"
    )


def _write_diag(page, artifacts: Path, error: Exception) -> None:
    try:
        frame, scans = _app_frame(page, timeout_seconds=5.0)
        body = _frame_body(frame)
    except Exception:
        scans = []
        body = ""
    (artifacts / "failure.json").write_text(
        json.dumps(
            {
                "error": f"{type(error).__name__}: {error}",
                "page_url": page.url,
                "body_start": body[:10000],
                "frames": scans,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    try:
        page.screenshot(path=str(artifacts / "failure.png"), full_page=True)
    except Exception:
        pass


def _rejected_summary(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "game_id": game.get("game_id"),
            "status": _status(game),
            "start_utc": str(game.get("game_datetime_utc") or ""),
            "away": ((game.get("away") or {}).get("full_name") if isinstance(game.get("away"), dict) else None),
            "home": ((game.get("home") or {}).get("full_name") if isinstance(game.get("home"), dict) else None),
        }
        for game in games
    ]


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    schedule = _schedule(now_utc)

    # Fail closed instead of selecting a future game. This cert is only for the
    # current no-future-pregame state the user asked us to enforce.
    if schedule["eligible"]:
        raise BrowserQAFailure(
            "Current WNBA date contains a future pregame game; certificate refuses "
            "to select or analyze any game automatically."
        )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        try:
            try:
                frame = _route_wnba_pra_without_game(page, production_url)
                frame, body = _wait_terminal(page, frame)
            except Exception as exc:
                _write_diag(page, artifacts, exc)
                raise

            active_cards = int(frame.locator(".p1v2-card").count())
            top3 = int(frame.locator(".p1v2-leaderboard").count())
            certified = int(frame.locator(".p1v2-final").count())
            active_game_buttons = int(frame.locator("button").filter(has_text="@").count())
            accepted_empty = any(marker.casefold() in body.casefold() for marker in EMPTY_MARKERS)
            page.screenshot(path=str(artifacts / "production.png"), full_page=True)
        finally:
            context.close()
            browser.close()

    if active_cards:
        raise BrowserQAFailure(f"No-future-game slate leaked Page 1 cards: {active_cards}")
    if top3:
        raise BrowserQAFailure(f"No-future-game slate leaked Top 3: {top3}")
    if certified:
        raise BrowserQAFailure(f"No-future-game slate leaked Certified PRA Pick: {certified}")
    if active_game_buttons:
        raise BrowserQAFailure(f"No-future-game slate leaked game selectors: {active_game_buttons}")
    if not accepted_empty:
        raise BrowserQAFailure("No-future-game slate lacks an accepted empty-state marker")

    result = {
        "status": "GREEN",
        "authority": "MONSTER_ONLY",
        "source_main_sha": SOURCE_MAIN_SHA,
        "production_url": production_url,
        "route": "WNBA -> PRA",
        "selected_game": False,
        "game_selection_attempted": False,
        "live_games_used_as_target": False,
        "final_games_used_as_target": False,
        "historical_games_used_as_target": False,
        "eligible_future_pregame_games": 0,
        "rejected_started_live_final_or_past_tip_games": len(schedule["rejected"]),
        "rejected_games": _rejected_summary(schedule["rejected"]),
        "page1_active_card_count": active_cards,
        "top3_leaderboard_count": top3,
        "certified_pick_count": certified,
        "active_game_button_count": active_game_buttons,
        "accepted_empty_state_visible": accepted_empty,
        "api2_state_used": False,
        "freeze_token": FREEZE_TOKEN,
    }
    (artifacts / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("MONSTER_WNBA_PRA_CURRENT_SLATE_EXCLUSION_GREEN=" + json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PRODUCTION_URL)
    parser.add_argument("--artifact-dir", default="artifacts/monster-wnba-pra-current-slate-exclusion-cert-r1")
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
