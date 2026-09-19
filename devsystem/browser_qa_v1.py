"""DevSystem automated browser QA for the local Streamlit branch build.

The browser QA proves that the checked-out branch can:
- boot Streamlit;
- expose the expected sport choices;
- enter the certified College Football -> Over/Under fast route directly;
- render the active Clean Page V39 compact evidence dashboard;
- expose V39's compact matchup foundation and frozen-model presentation strip;
- preserve 0.0% sportsbook projection influence and mutation-off boundaries;
- expose the compact Steps 5-10 evidence flow and Steps 11-12 certification shell;
- open the certified College Football -> Game Total exact-event route;
- require the real Step 5 Pace & Expected Possessions DOM surface;
- do so without obvious Python/runtime error text.

Dynamic schedule/odds availability is not required here because those are
production/data-contract responsibilities handled by the regression and later
production-verification layers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlencode

import requests
from playwright.sync_api import sync_playwright

DEFAULT_BASE_URL = "http://127.0.0.1:8501"
REQUIRED_SPORTS = (
    "MLB",
    "WNBA",
    "NFL",
    "College Football",
)
CFB_SPORT = "College Football"
CFB_MARKET = "Over/Under"
CFB_MARKET_LABEL = "🎯 CFB Market"
CFB_GAME_TOTAL_MARKET = "Game Total"
CFB_GAME_TOTAL_DATE = "2026-09-18"
CFB_GAME_TOTAL_EVENT_ID = "401858226"
CFB_GAME_TOTAL_STEP5_MARKER = "CFB_GAME_TOTAL_STEP5_PACE_POSSESSIONS_ACTIVE"
CFB_GAME_TOTAL_STEP5_ROOT_SELECTOR = (
    'details.gt168-step5[data-testid="gt157-step-5"]'
    f'[data-step5-marker="{CFB_GAME_TOTAL_STEP5_MARKER}"]'
)
CFB_REQUIRED_MARKERS = (
    "CFB O/U • CLEAN PAGE V39 ACTIVE",
    "COMPACT EVIDENCE RENDERER",
    "VERIFIED IDENTITY ≠ MISSING STEP METRIC",
    "0.0% SPORTSBOOK PROJECTION INFLUENCE",
    "Matchup Foundation",
    "Steps 1–4 • compact verified evidence",
    "Frozen O/U math • Mutation OFF • Sportsbook 0.0%",
    "Step 5 • Explosive Plays",
    "Step 10 • Historical Matchup",
    "Steps 11–12 • current form + certification",
)
FORBIDDEN_ERROR_MARKERS = (
    "Traceback (most recent call last)",
    "ModuleNotFoundError",
    "ImportError:",
    "SyntaxError:",
    "NameError:",
    "KeyError:",
    "This app has encountered an error",
)
SELECTOR_TIMEOUT_MS = 5000
CFB_RERUN_TIMEOUT_MS = 30000


class BrowserQAFailure(RuntimeError):
    pass


def _artifact_dir(path: str | Path) -> Path:
    result = Path(path)
    result.mkdir(parents=True, exist_ok=True)
    return result


def _cfb_over_under_url(base_url: str) -> str:
    query = urlencode(
        (
            ("ks_sport", CFB_SPORT),
            ("ks_cfb_market", CFB_MARKET),
        )
    )
    return base_url.rstrip("/") + "/?" + query


def _cfb_game_total_url(base_url: str) -> str:
    query = urlencode(
        (
            ("ks_sport", CFB_SPORT),
            ("ks_cfb_market", CFB_GAME_TOTAL_MARKET),
            ("ks_cfb_game_total_date", CFB_GAME_TOTAL_DATE),
            ("ks_cfb_game_total_event_id", CFB_GAME_TOTAL_EVENT_ID),
        )
    )
    return base_url.rstrip("/") + "/?" + query


def _wait_for_game_total_step5(frame, timeout_seconds: float = 90.0) -> dict[str, Any]:
    root = frame.locator(CFB_GAME_TOTAL_STEP5_ROOT_SELECTOR).last
    try:
        root.wait_for(
            state="attached",
            timeout=int(timeout_seconds * 1000),
        )
    except Exception as exc:
        try:
            body = frame.locator("body").inner_text(timeout=5000)
        except Exception:
            body = ""
        forbidden = _body_has_forbidden_error(body)
        detail = f" runtime_error={forbidden!r}" if forbidden else ""
        raise BrowserQAFailure(
            "Game Total Step 5 DOM did not attach."
            f"{detail} Body start={body[:4000]!r}"
        ) from exc

    body = frame.locator("body").inner_text(timeout=5000)
    forbidden = _body_has_forbidden_error(body)
    if forbidden:
        raise BrowserQAFailure(
            f"Game Total route contains runtime error marker: {forbidden}"
        )

    marker = root.get_attribute("data-step5-marker") or ""
    state = root.get_attribute("data-step5-state") or ""
    coverage = root.get_attribute("data-step5-coverage") or ""
    tiles = root.locator('[data-testid="gt168-step5-stat-tile"]')
    tile_count = tiles.count()
    ready_tiles = tiles.locator('[data-ready="true"]').count()

    if marker != CFB_GAME_TOTAL_STEP5_MARKER:
        raise BrowserQAFailure(
            f"Game Total Step 5 marker mismatch: {marker!r}"
        )
    if state != "READY":
        raise BrowserQAFailure(
            f"Game Total Step 5 state is not READY: {state!r}"
        )
    if coverage != "100":
        raise BrowserQAFailure(
            f"Game Total Step 5 coverage is not 100: {coverage!r}"
        )
    if tile_count != 12 or ready_tiles != 12:
        raise BrowserQAFailure(
            "Game Total Step 5 tile completeness failed: "
            f"tiles={tile_count} ready_tiles={ready_tiles}"
        )

    return {
        "body": body,
        "marker": marker,
        "state": state,
        "coverage": coverage,
        "tile_count": tile_count,
        "ready_tiles": ready_tiles,
    }


def _wait_for_health(base_url: str, timeout_seconds: float = 120.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    root_status: int | None = None
    health_status: int | None = None

    while time.monotonic() < deadline:
        try:
            health = requests.get(
                base_url.rstrip("/") + "/_stcore/health",
                timeout=5,
                headers={"User-Agent": "KyreSportsAI-DevSystem-BrowserQA/1.0"},
            )
            health_status = health.status_code
            root = requests.get(
                base_url.rstrip("/") + "/",
                timeout=10,
                headers={"User-Agent": "KyreSportsAI-DevSystem-BrowserQA/1.0"},
            )
            root_status = root.status_code
            if (
                health.status_code == 200
                and root.status_code == 200
                and "streamlit" in root.text.casefold()
            ):
                return {
                    "root_http": root.status_code,
                    "health_http": health.status_code,
                }
        except Exception as exc:  # pragma: no cover - exercised in CI/browser
            last_error = exc
        time.sleep(2)

    raise BrowserQAFailure(
        "Streamlit local health never became ready: "
        f"root={root_status} health={health_status} last_error={last_error!r}"
    )


def _body_has_forbidden_error(body: str) -> str | None:
    for marker in FORBIDDEN_ERROR_MARKERS:
        if marker in body:
            return marker
    return None


def _find_app_frame(page, timeout_seconds: float = 90.0):
    deadline = time.monotonic() + timeout_seconds
    last_scan: list[dict[str, Any]] = []

    while time.monotonic() < deadline:
        scans: list[dict[str, Any]] = []
        for index, frame in enumerate(page.frames):
            try:
                body = frame.locator("body").inner_text(timeout=5000)
            except Exception:
                body = ""
            try:
                combo_count = frame.get_by_role("combobox").count()
            except Exception:
                combo_count = 0

            scans.append(
                {
                    "index": index,
                    "url": frame.url,
                    "comboboxes": combo_count,
                    "body_start": body[:500],
                }
            )

            if "get this app back up" in body.casefold():
                wake = frame.get_by_text("Yes, get this app back up!", exact=False)
                if wake.count() > 0:
                    wake.click()
                    page.wait_for_timeout(5000)
                    continue

            if combo_count >= 1 and (
                "KYRE SPORTS AI" in body
                or "🏟️ Sport" in body
                or "Sport" in body
            ):
                return frame, scans

        last_scan = scans
        page.wait_for_timeout(2500)

    raise BrowserQAFailure(
        "Could not find rendered Streamlit app frame. "
        + json.dumps(last_scan, ensure_ascii=False)
    )


def _wait_for_text(frame, text: str, timeout_seconds: float = 45.0) -> str:
    marker = frame.get_by_text(text, exact=False).first
    try:
        marker.wait_for(
            state="visible",
            timeout=int(timeout_seconds * 1000),
        )
    except Exception as exc:
        try:
            body = frame.locator("body").inner_text(timeout=5000)
        except Exception:
            body = ""
        raise BrowserQAFailure(
            f"Timed out waiting for text {text!r}. Body start={body[:3000]!r}"
        ) from exc
    return frame.locator("body").inner_text(timeout=5000)


def _read_sport_options(page, frame) -> list[str]:
    combo = frame.get_by_role("combobox").nth(0)
    combo.click()
    options_locator = page.get_by_role("option")
    options_locator.first.wait_for(state="visible", timeout=SELECTOR_TIMEOUT_MS)
    options = [
        value.strip()
        for value in options_locator.all_inner_texts()
        if value.strip()
    ]
    page.keyboard.press("Escape")
    return options


def _choose(page, frame, combo_index: int, value: str) -> None:
    combos = frame.get_by_role("combobox")
    if combos.count() <= combo_index:
        raise BrowserQAFailure(
            f"Expected combobox index {combo_index}; found {combos.count()}"
        )
    combo = combos.nth(combo_index)
    combo.click()
    page.keyboard.type(value)
    page.keyboard.press("Enter")


def run_browser_qa(
    *,
    base_url: str = DEFAULT_BASE_URL,
    artifact_dir: str | Path = "artifacts/browser-qa",
) -> dict[str, Any]:
    artifacts = _artifact_dir(artifact_dir)
    health = _wait_for_health(base_url)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1400})

        try:
            page.goto(
                base_url.rstrip("/") + "/",
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, initial_scan = _find_app_frame(page)

            initial_body = frame.locator("body").inner_text()
            forbidden = _body_has_forbidden_error(initial_body)
            if forbidden:
                raise BrowserQAFailure(
                    f"Initial app body contains runtime error marker: {forbidden}"
                )

            options = _read_sport_options(page, frame)
            missing_sports = [
                sport for sport in REQUIRED_SPORTS
                if sport not in options
            ]
            if missing_sports:
                raise BrowserQAFailure(
                    f"Sport selector is missing {missing_sports}; saw {options}"
                )

            # Use a fresh Streamlit browser session for the exact certified O/U
            # route. Clicking College Football first briefly renders default CFB
            # Moneyline, whose cfb_* purge/re-import graph can race before the
            # browser reaches Over/Under. V154/V77 already certify these exact
            # query parameters for cold-start route restoration.
            page.close()
            page = browser.new_page(viewport={"width": 1440, "height": 1400})
            page.goto(_cfb_over_under_url(base_url),
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, route_scan = _find_app_frame(page)

            cfb_market_combo = frame.get_by_role(
                "combobox",
                name=CFB_MARKET_LABEL,
                exact=True,
            )
            cfb_market_combo.wait_for(
                state="visible",
                timeout=CFB_RERUN_TIMEOUT_MS,
            )

            body = _wait_for_text(frame, CFB_REQUIRED_MARKERS[-1], 60.0)

            missing_markers = [
                marker for marker in CFB_REQUIRED_MARKERS
                if marker not in body
            ]
            if missing_markers:
                raise BrowserQAFailure(
                    "CFB Clean Page V39 presentation marker drift: "
                    + " | ".join(missing_markers)
                )

            forbidden = _body_has_forbidden_error(body)
            if forbidden:
                raise BrowserQAFailure(
                    f"CFB route contains runtime error marker: {forbidden}"
                )

            over_under_screenshot = artifacts / "browser_qa_over_under_green.png"
            page.screenshot(path=str(over_under_screenshot), full_page=True)

            # Exact production-shaped Game Total regression. This is intentionally
            # a fresh Streamlit browser session so route/session persistence from
            # Over/Under cannot hide a Game Total boot/runtime failure.
            page.close()
            page = browser.new_page(viewport={"width": 1440, "height": 1600})
            page.goto(
                _cfb_game_total_url(base_url),
                wait_until="domcontentloaded",
                timeout=120000,
            )
            game_total_frame, game_total_scan = _find_app_frame(page)
            # The version marker is intentionally emitted as a hidden/build
            # marker and is not guaranteed to be "visible" text. Prove the
            # actual Step 5 DOM surface directly instead.
            game_total_step5 = _wait_for_game_total_step5(
                game_total_frame,
                90.0,
            )
            game_total_body = game_total_step5["body"]

            game_total_screenshot = artifacts / "browser_qa_game_total_step5_green.png"
            page.screenshot(path=str(game_total_screenshot), full_page=True)

            result = {
                "status": "GREEN",
                "base_url": base_url,
                "root_http": health["root_http"],
                "health_http": health["health_http"],
                "required_sports": list(REQUIRED_SPORTS),
                "observed_sports": options,
                "cfb_route": f"{CFB_SPORT} -> {CFB_MARKET}",
                "cfb_markers": list(CFB_REQUIRED_MARKERS),
                "app_frame_url": frame.url,
                "frame_scan_count": len(initial_scan) + len(route_scan),
                "screenshot": str(over_under_screenshot),
                "game_total_route": f"{CFB_SPORT} -> {CFB_GAME_TOTAL_MARKET}",
                "game_total_event_id": CFB_GAME_TOTAL_EVENT_ID,
                "game_total_date": CFB_GAME_TOTAL_DATE,
                "game_total_step5_marker": game_total_step5["marker"],
                "game_total_step5_state": game_total_step5["state"],
                "game_total_step5_coverage": game_total_step5["coverage"],
                "game_total_step5_tile_count": game_total_step5["tile_count"],
                "game_total_step5_ready_tiles": game_total_step5["ready_tiles"],
                "game_total_app_frame_url": game_total_frame.url,
                "game_total_frame_scan_count": len(game_total_scan),
                "game_total_screenshot": str(game_total_screenshot),
            }
            print("DEVSYSTEM_BROWSER_QA_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        except Exception:
            failure = artifacts / "browser_qa_failure.png"
            try:
                page.screenshot(path=str(failure), full_page=True)
            except Exception:
                pass
            raise
        finally:
            browser.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/browser-qa",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_browser_qa(
        base_url=args.base_url,
        artifact_dir=args.artifact_dir,
    )
