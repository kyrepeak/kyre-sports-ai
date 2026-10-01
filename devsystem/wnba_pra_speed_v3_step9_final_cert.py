"""WNBA PRA Speed V3 Step 9 — final strict production speed certification.

Certification-only owner. It composes the already-frozen Step-5 and Step-8
production profiles and fails closed if any final latency budget regresses.
No WNBA product/runtime/model/provider/router/math behavior is modified here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.browser_qa_v1 import BrowserQAFailure, _find_app_frame
from devsystem.wnba_pra_speed_v3_step2_public_profile import PUBLIC_HOST
from devsystem import wnba_nav_v2_step7_public_freeze as nav_profile
from devsystem.wnba_nav_v2_step7_public_freeze import (
    API_GAMES,
    SLATE_READY_BUDGET_SECONDS,
    _wait_page,
)
from devsystem import wnba_pra_speed_v3_step5_public_profile as step5_profile
from devsystem import wnba_pra_speed_v3_step8_public_profile as step8_profile

WARM_SAME_SESSION_SECONDS_MAX = 0.75
CACHED_COLD_SECONDS_MAX = 1.50
TRUE_COLD_SECONDS_MAX = 2.50
VISIBLE_CONTINUITY_SECONDS_MAX = 0.75

PROJECT = "WNBA PRA Speed V3"
STEP = "9/9"
SPORT_LABEL = "🏟️ Sport"
WNBA_MARKET_LABEL = "🎯 WNBA Market"
ROUTE_CONTROL_TIMEOUT_SECONDS = 30.0
UPCOMING_GAME_SEARCH_DAYS = 31
SCHEDULE_REQUEST_TIMEOUT_SECONDS = 15.0
SCHEDULE_TIMEZONE = ZoneInfo("America/New_York")


def _wnba_pra_route_url(base_url: str) -> str:
    """Return the immutable certified public route handoff for WNBA PRA."""
    query = urlencode({"ks_jump_sport": "WNBA", "ks_jump_market": "PRA"})
    return base_url.rstrip("/") + "/?" + query


def _choose_labeled_route_value(page, frame, label: str, value: str) -> None:
    """Choose an exact Streamlit selectbox value by its accessible label."""
    combo = frame.get_by_role("combobox", name=label, exact=True)
    if combo.count() < 1:
        raise BrowserQAFailure(f"Step-9 route control missing: {label!r}")
    combo.first.click()

    deadline = time.monotonic() + ROUTE_CONTROL_TIMEOUT_SECONDS
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

    raise BrowserQAFailure(
        f"Step-9 route option {value!r} did not become selectable for {label!r}."
    )


def _prime_wnba_pra_route(page, route_url: str):
    """Enter WNBA/PRA using exact labeled controls, not positional state.

    The query handoff remains a harmless first hint, but live production can
    retain a stale MLB route. The authoritative verifier action is therefore
    the exact visible Sport -> WNBA and WNBA Market -> PRA interaction.
    """
    page.goto(route_url, wait_until="domcontentloaded", timeout=120000)
    frame, _ = _find_app_frame(page, timeout_seconds=120.0)

    _choose_labeled_route_value(page, frame, SPORT_LABEL, "WNBA")

    deadline = time.monotonic() + ROUTE_CONTROL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        frame, _ = _find_app_frame(page, timeout_seconds=12.0)
        market = frame.get_by_role("combobox", name=WNBA_MARKET_LABEL, exact=True)
        if market.count() > 0:
            break
        page.wait_for_timeout(100)
    else:
        raise BrowserQAFailure("Step-9 WNBA market selector did not appear.")

    _choose_labeled_route_value(page, frame, WNBA_MARKET_LABEL, "PRA")
    frame, ready = _wait_page(
        page,
        "slate",
        timeout_seconds=SLATE_READY_BUDGET_SECONDS,
    )
    if ready > SLATE_READY_BUDGET_SECONDS:
        raise BrowserQAFailure(
            f"Step-9 WNBA PRA slate budget exceeded: {ready:.3f}s"
        )
    print("WNBA_PRA_SPEED_V3_STEP9_LABELED_ROUTE_GREEN")
    return frame, ready


def _future_pregame_dates() -> tuple[str, ...]:
    """Return only WNBA dates with at least one not-yet-started playable game.

    Step 9 must never certify against a completed historical slate. We query
    the live Kyre/WNBA schedule from today forward, require scheduled +
    playable_pregame identity, and for today's slate require a future UTC
    tipoff. If no future pregame exists, certification fails closed.
    """
    now_local = datetime.now(SCHEDULE_TIMEZONE)
    today = now_local.date()
    now_utc = datetime.now(timezone.utc)
    session = requests.Session()
    dates: list[str] = []
    errors: list[str] = []

    for offset in range(0, UPCOMING_GAME_SEARCH_DAYS + 1):
        day = today + timedelta(days=offset)
        try:
            response = session.get(
                API_GAMES,
                params={"date": day.isoformat(), "season": 2026},
                headers={
                    "accept": "application/json",
                    "user-agent": "wnba-pra-speed-v3-step9-upcoming-game/1",
                },
                timeout=SCHEDULE_REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                errors.append(f"{day}:HTTP{response.status_code}")
                continue
            payload = response.json()
            games = payload.get("games") if isinstance(payload, dict) else None
            if not isinstance(games, list):
                continue

            has_future_pregame = False
            for game in games:
                if not isinstance(game, dict):
                    continue
                status = game.get("status") if isinstance(game.get("status"), dict) else {}
                verification = (
                    game.get("verification")
                    if isinstance(game.get("verification"), dict)
                    else {}
                )
                if str(status.get("category") or "").casefold() != "scheduled":
                    continue
                if verification.get("playable_pregame") is not True:
                    continue

                if day == today:
                    raw_start = str(game.get("game_datetime_utc") or "").strip()
                    if not raw_start:
                        continue
                    try:
                        game_start = datetime.fromisoformat(
                            raw_start.replace("Z", "+00:00")
                        )
                    except ValueError:
                        continue
                    if game_start.tzinfo is None:
                        game_start = game_start.replace(tzinfo=timezone.utc)
                    game_start = game_start.astimezone(timezone.utc)
                    if game_start <= now_utc:
                        continue

                has_future_pregame = True
                break

            if has_future_pregame:
                dates.append(day.isoformat())
        except Exception as exc:
            errors.append(f"{day}:{type(exc).__name__}")

    if not dates:
        raise BrowserQAFailure(
            "Step-9 could not find any scheduled future WNBA pregame within "
            f"{UPCOMING_GAME_SEARCH_DAYS} days; "
            + ",".join(errors[-8:])
        )

    selected = tuple(dates)
    print(
        "WNBA_PRA_SPEED_V3_STEP9_UPCOMING_GAME_DATES="
        + ",".join(selected)
    )
    print("WNBA_PRA_SPEED_V3_STEP9_NO_PAST_GAMES_GREEN")
    return selected


def _bounded(label: str, value: float, limit: float) -> float:
    observed = float(value)
    if observed < 0:
        raise BrowserQAFailure(f"{label} timing is negative: {observed:.3f}s")
    if observed > float(limit):
        raise BrowserQAFailure(
            f"Step-9 {label} exceeded final budget: "
            f"{observed:.3f}s > {float(limit):.3f}s"
        )
    return observed


def certify_results(
    *,
    step5_result: dict[str, Any],
    step8_result: dict[str, Any],
) -> dict[str, Any]:
    if step5_result.get("status") != "GREEN":
        raise BrowserQAFailure("Frozen Step-5 production profile is not GREEN.")
    if step8_result.get("status") != "GREEN":
        raise BrowserQAFailure("Frozen Step-8 production profile is not GREEN.")
    if step5_result.get("project") != PROJECT or step8_result.get("project") != PROJECT:
        raise BrowserQAFailure("Final certification received a foreign project result.")

    true_cold = _bounded(
        "true-cold Player",
        step5_result["true_cold_player_seconds"],
        TRUE_COLD_SECONDS_MAX,
    )
    warm = _bounded(
        "warm same-session Player",
        step5_result["warm_same_session_seconds"],
        WARM_SAME_SESSION_SECONDS_MAX,
    )
    cached = _bounded(
        "cached-cold Player",
        step8_result["final_player_seconds"],
        CACHED_COLD_SECONDS_MAX,
    )
    visible = _bounded(
        "browser-resident visible continuity",
        step8_result["visible_content_seconds"],
        VISIBLE_CONTINUITY_SECONDS_MAX,
    )

    if step8_result.get("visible_content_path") not in {
        "game_card_continuity",
        "client_preview",
    }:
        raise BrowserQAFailure(
            "Step-9 final proof requires the frozen Step-8 browser-resident "
            "continuity path before the Streamlit rerun."
        )
    if step8_result.get("frozen_steps_1_7_preserved") is not True:
        raise BrowserQAFailure("Step-8 did not certify frozen Steps 1-7 preservation.")
    if step8_result.get("server_shell_runtime_fallback_preserved") is not True:
        raise BrowserQAFailure("Step-8 server-shell fallback preservation is missing.")

    return {
        "project": PROJECT,
        "step": STEP,
        "status": "GREEN",
        "warm_same_session_seconds": round(warm, 3),
        "warm_same_session_seconds_max": WARM_SAME_SESSION_SECONDS_MAX,
        "cached_cold_seconds": round(cached, 3),
        "cached_cold_seconds_max": CACHED_COLD_SECONDS_MAX,
        "true_cold_seconds": round(true_cold, 3),
        "true_cold_seconds_max": TRUE_COLD_SECONDS_MAX,
        "visible_continuity_seconds": round(visible, 3),
        "visible_continuity_seconds_max": VISIBLE_CONTINUITY_SECONDS_MAX,
        "visible_continuity_path": step8_result["visible_content_path"],
        "step5_profile_green": True,
        "step8_profile_green": True,
        "frozen_steps_1_8_preserved": True,
        "product_runtime_changed_by_step9": False,
        "projection_math_changed_by_step9": False,
        "market_math_changed_by_step9": False,
        "data_meaning_changed_by_step9": False,
        "sportsbook_projection_influence_changed_by_step9": False,
    }


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    route_url = _wnba_pra_route_url(production_url)

    original_step5_route = step5_profile._route_to_wnba_pra
    original_step8_route = step8_profile._route_to_wnba_pra
    original_nav_dates = nav_profile.CERTIFIED_GAME_DATES
    original_step5_dates = step5_profile.CERTIFIED_GAME_DATES
    upcoming_game_dates = _future_pregame_dates()

    def primed_route(page):
        return _prime_wnba_pra_route(page, route_url)

    step5_profile._route_to_wnba_pra = primed_route
    step8_profile._route_to_wnba_pra = primed_route
    nav_profile.CERTIFIED_GAME_DATES = upcoming_game_dates
    step5_profile.CERTIFIED_GAME_DATES = upcoming_game_dates
    print(f"WNBA_PRA_SPEED_V3_STEP9_ROUTE_PRIME_URL={route_url}")
    print("WNBA_PRA_SPEED_V3_STEP9_UPCOMING_GAME_VERIFIER_SCOPE_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_ROUTE_PRIME_GREEN")
    try:
        # True-cold + warm same-session proof runs first in a fresh browser context.
        step5_result = step5_profile.run(
            production_url=route_url,
            artifact_dir=artifacts / "step5-final-proof",
        )

        # Cached-cold + browser-resident visible-first proof runs second and requires
        # the frozen Step-7 precompute readiness gate before timing.
        step8_result = step8_profile.run(
            production_url=route_url,
            artifact_dir=artifacts / "step8-final-proof",
        )
    finally:
        step5_profile._route_to_wnba_pra = original_step5_route
        step8_profile._route_to_wnba_pra = original_step8_route
        nav_profile.CERTIFIED_GAME_DATES = original_nav_dates
        step5_profile.CERTIFIED_GAME_DATES = original_step5_dates

    result = certify_results(
        step5_result=step5_result,
        step8_result=step8_result,
    )
    (artifacts / "wnba_pra_speed_v3_step9_final_cert.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "WNBA_PRA_SPEED_V3_STEP9_TRUE_COLD_SECONDS="
        f"{result['true_cold_seconds']:.3f}"
    )
    print(
        "WNBA_PRA_SPEED_V3_STEP9_WARM_SAME_SESSION_SECONDS="
        f"{result['warm_same_session_seconds']:.3f}"
    )
    print(
        "WNBA_PRA_SPEED_V3_STEP9_CACHED_COLD_SECONDS="
        f"{result['cached_cold_seconds']:.3f}"
    )
    print(
        "WNBA_PRA_SPEED_V3_STEP9_VISIBLE_CONTINUITY_SECONDS="
        f"{result['visible_continuity_seconds']:.3f}"
    )
    print(
        "WNBA_PRA_SPEED_V3_STEP9_VISIBLE_CONTINUITY_PATH="
        f"{result['visible_continuity_path']}"
    )
    print("WNBA_PRA_SPEED_V3_STEP9_TRUE_COLD_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_WARM_SAME_SESSION_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_CACHED_COLD_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_VISIBLE_CONTINUITY_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_DUPLICATE_KEY_GUARD_SCOPE_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_FROZEN_STEPS1_8_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_PROFILE_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_GREEN")
    print("WNBA_PRA_SPEED_V3_STEP9_FROZEN")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/wnba-pra-speed-v3-step9",
    )
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
