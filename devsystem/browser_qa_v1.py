"""DevSystem automated browser QA for the local Streamlit branch build.

The browser QA proves that the checked-out branch can:
- boot Streamlit;
- expose the expected sport choices;
- route to College Football -> Over/Under;
- render the active Clean Page V29 readable Step 12 final-certification shell;
- preserve the freshness firewall, 0.0% market influence, and frozen projection marker;
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
CFB_REQUIRED_MARKERS = (
    "CFB O/U • CLEAN PAGE V20 ACTIVE",
    "STEP 6 MARKET INTELLIGENCE LIVE",
    "FRESHNESS FIREWALL ACTIVE",
    "0.0% PROJECTION INFLUENCE",
    "FROZEN PROJECTION MATH PRESERVED",
    "READABLE STEP 9 GAME-DAY ENVIRONMENT ACTIVE",
    "READABLE STEP 10 HISTORICAL MATCHUP ACTIVE",
    "READABLE STEP 11 CURRENT FORM + SCHEDULE STRENGTH ACTIVE",
    "READABLE STEP 12 FINAL CERTIFICATION ACTIVE",
)
FORBIDDEN_ERROR_MARKERS = (
    "Traceback (most recent call last)",
    "ModuleNotFoundError",
    "ImportError:",
    "SyntaxError:",
    "NameError:",
)


class BrowserQAFailure(RuntimeError):
    pass


def _artifact_dir(path: str | Path) -> Path:
    result = Path(path)
    result.mkdir(parents=True, exist_ok=True)
    return result


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
    deadline = time.monotonic() + timeout_seconds
    last_body = ""
    while time.monotonic() < deadline:
        try:
            last_body = frame.locator("body").inner_text(timeout=5000)
        except Exception:
            last_body = ""
        if text in last_body:
            return last_body
        page = frame.page
        page.wait_for_timeout(1500)
    raise BrowserQAFailure(
        f"Timed out waiting for text {text!r}. Body start={last_body[:3000]!r}"
    )


def _read_sport_options(page, frame) -> list[str]:
    combo = frame.get_by_role("combobox").nth(0)
    combo.click()
    page.wait_for_timeout(500)
    options = [
        value.strip()
        for value in page.get_by_role("option").all_inner_texts()
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
    page.wait_for_timeout(250)
    page.keyboard.type(value)
    page.keyboard.press("Enter")
    page.wait_for_timeout(1800)


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
            frame, scan = _find_app_frame(page)

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

            _choose(page, frame, 0, CFB_SPORT)

            deadline = time.monotonic() + 30.0
            while time.monotonic() < deadline:
                if frame.get_by_role("combobox").count() >= 2:
                    break
                page.wait_for_timeout(1000)
            else:
                raise BrowserQAFailure(
                    "CFB route did not expose a market combobox"
                )

            _choose(page, frame, 1, CFB_MARKET)
            body = _wait_for_text(frame, CFB_REQUIRED_MARKERS[0], 60.0)

            missing_markers = [
                marker for marker in CFB_REQUIRED_MARKERS
                if marker not in body
            ]
            if missing_markers:
                raise BrowserQAFailure(
                    "CFB Clean Page V29 Step 12 marker drift: "
                    + " | ".join(missing_markers)
                )

            forbidden = _body_has_forbidden_error(body)
            if forbidden:
                raise BrowserQAFailure(
                    f"CFB route contains runtime error marker: {forbidden}"
                )

            screenshot = artifacts / "browser_qa_green.png"
            page.screenshot(path=str(screenshot), full_page=True)

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
                "frame_scan_count": len(scan),
                "screenshot": str(screenshot),
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
