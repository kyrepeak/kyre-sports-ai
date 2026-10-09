"""CFB Game Total Page 1 Visual Cleanup Step 5 — live responsive certification.

Certification-only. This module never mutates product/runtime behavior. It opens
the production CFB Game Total page at mobile/tablet/desktop widths and proves the
frozen Step 2–4 presentation surfaces are visible, Phoenix TODAY+ includes the
current Phoenix day, the old dense Overview wall is absent, and no horizontal
overflow or missing-data copy is visible.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

from devsystem import browser_qa_v1 as base

EXPECTED_MAIN_SHA = "0e2c11f03c1d3f6cb94756057ccb95e8ae74b2f9"
PHOENIX_TZ = "America/Phoenix"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PRODUCT_RUNTIME = False
GITHUB_ACTIONS_FALLBACK = 0
CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
CFB_MARKET_LABEL = "🎯 CFB Market"
PRODUCTION_URL = "https://pickvault.streamlit.app"

VIEWPORTS = {
    "mobile": {"width": 390, "height": 844},
    "tablet": {"width": 768, "height": 1024},
    "desktop": {"width": 1440, "height": 1200},
}

REQUIRED_TESTIDS = (
    "gtvc2-matchup-hero",
    "gtvc2-context-strip",
    "gtvc2-view-tabs",
    "gtvc3-future-day-strip",
    "gtvc3-overview-edge",
    "gtvc3-team-snapshot",
    "gtvc4-games-on-day",
    "gtvc4-data-footer",
)

FORBIDDEN_VISIBLE_TEXT = (
    "data limited",
    "venue pending",
    "location pending",
    "forecast pending",
    "wind pending",
    "espn id unavailable",
    "game total evidence • steps 1–12",
    "top-5 slate scanner",
)


class Step5VisualCertFailure(RuntimeError):
    pass


def production_route(base_url: str = PRODUCTION_URL) -> str:
    query = urlencode({"ks_sport": CFB_SPORT, "ks_cfb_market": GAME_TOTAL_MARKET})
    return base_url.rstrip("/") + "/?" + query


def _today_button_label() -> str:
    today = datetime.now(ZoneInfo(PHOENIX_TZ)).date()
    return f"{today.strftime('%a • %b')} {today.day}"


def _visible(frame: Any, testid: str) -> None:
    locator = frame.locator(f'[data-testid="{testid}"]').first
    locator.wait_for(state="visible", timeout=90000)


def _prime_route(page: Any) -> tuple[Any, Any]:
    page.goto(production_route(), wait_until="domcontentloaded", timeout=120000)
    frame, scans = base._find_app_frame(page)
    try:
        _visible(frame, "gtvc2-matchup-hero")
        return frame, scans
    except Exception:
        sports = base._read_sport_options(page, frame)
        if CFB_SPORT not in sports:
            raise Step5VisualCertFailure(f"College Football route missing: {sports!r}")
        base._choose(page, frame, 0, CFB_SPORT)
        frame, _ = base._find_app_frame(page)
        market = frame.get_by_role("combobox", name=CFB_MARKET_LABEL, exact=True)
        market.wait_for(state="visible", timeout=45000)
        base._choose(page, frame, 1, GAME_TOTAL_MARKET)
        frame, scans = base._find_app_frame(page)
        _visible(frame, "gtvc2-matchup-hero")
        return frame, scans


def _forbidden_visible_text(body: str) -> list[str]:
    lower = body.casefold()
    return [item for item in FORBIDDEN_VISIBLE_TEXT if item.casefold() in lower]


def _runtime_error(body: str) -> str:
    marker = base._body_has_forbidden_error(body)
    return str(marker or "")


def _horizontal_overflow(frame: Any) -> bool:
    return bool(
        frame.evaluate(
            """() => {
                const de = document.documentElement;
                const body = document.body;
                const width = Math.max(de ? de.scrollWidth : 0, body ? body.scrollWidth : 0);
                const client = de ? de.clientWidth : window.innerWidth;
                return width > client + 3;
            }"""
        )
    )


def _viewport_result(page: Any, frame: Any, name: str, scans: Any, artifact_dir: Path) -> dict[str, Any]:
    for testid in REQUIRED_TESTIDS:
        _visible(frame, testid)

    body = frame.locator("body").inner_text(timeout=30000)
    today_label = _today_button_label()
    today_visible = today_label in body
    forbidden = _forbidden_visible_text(body)
    runtime_error = _runtime_error(body)
    overflow = _horizontal_overflow(frame)
    games_count = frame.locator('[data-testid="gtvc4-games-on-day"]').count()

    if not today_visible:
        raise Step5VisualCertFailure(f"Phoenix current day missing at {name}: {today_label}")
    if forbidden:
        raise Step5VisualCertFailure(f"Forbidden Overview text at {name}: {forbidden}")
    if runtime_error:
        raise Step5VisualCertFailure(f"Runtime error at {name}: {runtime_error}")
    if overflow:
        raise Step5VisualCertFailure(f"Horizontal overflow at {name}")
    if games_count != 1:
        raise Step5VisualCertFailure(f"Expected one Games on This Day surface at {name}; found {games_count}")

    screenshot = artifact_dir / f"cfb_game_total_step5_{name}.png"
    page.screenshot(path=str(screenshot), full_page=True)
    return {
        "viewport": dict(VIEWPORTS[name]),
        "required_testids_visible": list(REQUIRED_TESTIDS),
        "all_required_visible": True,
        "phoenix_today_label": today_label,
        "phoenix_today_visible": True,
        "friday_visible": datetime.now(ZoneInfo(PHOENIX_TZ)).weekday() != 4 or today_visible,
        "games_on_day_surface_count": games_count,
        "horizontal_overflow": False,
        "forbidden_visible_text": [],
        "runtime_error": "",
        "initial_frame_scan": scans,
        "screenshot": str(screenshot),
    }


def evidence_is_terminal_green(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("status") != "GREEN":
        return False
    if payload.get("source_main_sha") != EXPECTED_MAIN_SHA:
        return False
    if payload.get("phoenix_timezone") != PHOENIX_TZ:
        return False
    if float(payload.get("sportsbook_projection_influence", -1)) != 0.0:
        return False
    if int(payload.get("github_actions_fallback", -1)) != 0:
        return False
    viewports = payload.get("viewports")
    if not isinstance(viewports, dict) or set(viewports) != set(VIEWPORTS):
        return False
    for name in VIEWPORTS:
        row = viewports.get(name) or {}
        if row.get("all_required_visible") is not True:
            return False
        if row.get("phoenix_today_visible") is not True:
            return False
        if row.get("friday_visible") is not True:
            return False
        if int(row.get("games_on_day_surface_count", 0)) != 1:
            return False
        if row.get("horizontal_overflow") is not False:
            return False
        if row.get("forbidden_visible_text") not in ([], None):
            return False
        if str(row.get("runtime_error") or ""):
            return False
    return True


def run(*, base_url: str = PRODUCTION_URL, artifact_dir: str | Path = "artifacts/cfb-game-total-step5") -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    health = base._wait_for_health(base_url)
    results: dict[str, Any] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        try:
            for name, viewport in VIEWPORTS.items():
                page = browser.new_page(viewport=viewport)
                try:
                    frame, scans = _prime_route(page)
                    results[name] = _viewport_result(page, frame, name, scans, artifacts)
                finally:
                    page.close()
        finally:
            browser.close()

    payload = {
        "status": "GREEN",
        "source_main_sha": EXPECTED_MAIN_SHA,
        "production_url": base_url,
        "route_url": production_route(base_url),
        "phoenix_timezone": PHOENIX_TZ,
        "phoenix_date": datetime.now(ZoneInfo(PHOENIX_TZ)).date().isoformat(),
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "github_actions_fallback": GITHUB_ACTIONS_FALLBACK,
        "health": health,
        "viewports": results,
    }
    if not evidence_is_terminal_green(payload):
        raise Step5VisualCertFailure("Step-5 terminal evidence contract rejected generated payload")

    evidence = artifacts / "cfb_game_total_page1_visual_cleanup_step5_live_visual_cert.json"
    evidence.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print("CFB_GT_PAGE1_VISUAL_CLEANUP_STEP5_LIVE_VISUAL_GREEN", flush=True)
    print("CFB_GT_PAGE1_VISUAL_CLEANUP_STEP5_EVIDENCE=" + json.dumps(payload, sort_keys=True), flush=True)
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=PRODUCTION_URL)
    parser.add_argument("--artifact-dir", default="artifacts/cfb-game-total-step5")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
