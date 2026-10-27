"""MONSTER WNBA PRA upcoming-games-only production certification R1.

Read-only Step 2G browser proof. It never targets a live, final, started, or
historical game. The verifier discovers only future scheduled WNBA dates from
the Vercel Kyre Sports API surface, then drives PickVault WNBA -> PRA using the
already-proven public navigation helper and renders a real future pregame slate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import BrowserQAFailure
from devsystem import wnba_nav_v2_step7_public_freeze as nav
from devsystem import wnba_pra_speed_v3_step9_final_cert as speed9
from devsystem.wnba_pra_step3_public_freeze_v1 import _route_to_wnba_pra

PRODUCTION_URL = "https://pickvault.streamlit.app"
SCHEDULE_URL = "https://kyre-runless-proof.vercel.app/api/v1/wnba/games"
EASTERN = ZoneInfo("America/New_York")
SEARCH_DAYS = 31
REQUEST_TIMEOUT_SECONDS = 20.0
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
    """Return only future scheduled WNBA dates from Kyre Sports API/Vercel."""
    now_utc = datetime.now(timezone.utc)
    today = now_utc.astimezone(EASTERN).date()
    session = requests.Session()
    dates: list[str] = []
    errors: list[str] = []

    for offset in range(0, SEARCH_DAYS + 1):
        day = today + timedelta(days=offset)
        day_text = day.isoformat()
        try:
            response = session.get(
                SCHEDULE_URL,
                params={"date": day_text, "season": 2026},
                headers={
                    "accept": "application/json",
                    "user-agent": "monster-wnba-pra-future-pregame-cert/1",
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                errors.append(f"{day_text}:HTTP{response.status_code}")
                continue
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("source") != "WNBA Official Schedule":
                errors.append(f"{day_text}:IDENTITY")
                continue
            games = payload.get("games")
            if not isinstance(games, list):
                continue
            for raw in games:
                if not isinstance(raw, dict) or _status(raw) != "scheduled":
                    continue
                start = _start_utc(raw)
                if start is not None and start > now_utc:
                    dates.append(day_text)
                    break
        except Exception as exc:
            errors.append(f"{day_text}:{type(exc).__name__}")

    if not dates:
        raise BrowserQAFailure(
            "MONSTER cert found no future scheduled WNBA game via Kyre Sports API/Vercel "
            f"within {SEARCH_DAYS} days. errors={errors[:5]}"
        )
    return tuple(dates)


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    dates = _future_pregame_dates()
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    selected_date = ""
    game_count = 0
    body_excerpt = ""

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

            for target in dates:
                try:
                    frame = speed9._set_future_slate_date_segmented(page, frame, target)
                except Exception:
                    continue
                game_count = int(nav._game_button(frame).count())
                if game_count > 0:
                    selected_date = target
                    break

            if not selected_date:
                raise BrowserQAFailure(
                    "MONSTER cert could not render any discovered future pregame WNBA slate."
                )

            body_excerpt = nav._body(frame)[:5000]
            folded = body_excerpt.casefold()
            if "wnba" not in folded or "pra" not in folded:
                raise BrowserQAFailure("MONSTER cert left the WNBA/PRA public route.")

            page.screenshot(
                path=str(artifacts / "wnba-pra-future-pregame-production.png"),
                full_page=True,
            )
        finally:
            context.close()
            browser.close()

    result = {
        "status": "GREEN",
        "authority": "MONSTER_ONLY",
        "production_url": production_url,
        "route": "WNBA -> PRA",
        "schedule_source": "WNBA Official Schedule via Kyre Sports API/Vercel",
        "future_pregame_dates": list(dates),
        "selected_future_date": selected_date,
        "public_future_game_count": game_count,
        "live_games_used_as_target": False,
        "final_games_used_as_target": False,
        "historical_games_used_as_target": False,
        "future_pregame_only": True,
        "api2_state_used": False,
        "freeze_token": FREEZE_TOKEN,
    }
    (artifacts / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("MONSTER_WNBA_PRA_FUTURE_PREGAME_PRODUCTION_GREEN=" + json.dumps(result, sort_keys=True))
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
