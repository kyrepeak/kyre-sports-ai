"""DevSystem production verification.

This script verifies the real deployed public surfaces after a merge:
- Render API transport and health;
- the public CFB odds safety contract;
- the deployed Streamlit app shell;
- the College Football -> Over/Under V26 readable Step 9 environment route through a real browser.

Render deploy metadata/log freshness is inspected through the connected Render
tooling by the release operator/assistant. No Render API secret is required here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TARGETS_PATH = ROOT / "devsystem" / "production_targets_v1.json"

FORBIDDEN_ERROR_MARKERS = (
    "Traceback (most recent call last)",
    "ModuleNotFoundError",
    "ImportError:",
    "SyntaxError:",
    "NameError:",
)

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
)


class ProductionVerificationFailure(RuntimeError):
    pass


def _load_targets(path: Path = TARGETS_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if int(payload.get("version") or 0) != 1:
        raise ProductionVerificationFailure("production target registry version drift")
    return payload


def _request_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout_seconds: float = 60.0,
) -> tuple[int, dict[str, Any]]:
    response = session.get(url, params=params, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ProductionVerificationFailure(f"Expected JSON object from {url}")
    return response.status_code, payload


def _wait_http_200(
    session: requests.Session,
    url: str,
    *,
    timeout_seconds: float = 420.0,
    expect_text: str | None = None,
) -> int:
    deadline = time.monotonic() + timeout_seconds
    last: Exception | None = None
    last_status: int | None = None
    while time.monotonic() < deadline:
        try:
            response = session.get(url, timeout=30, allow_redirects=True)
            last_status = response.status_code
            if response.status_code == 200:
                if expect_text is None or expect_text.casefold() in response.text.casefold():
                    return response.status_code
        except Exception as exc:  # pragma: no cover - network/CI path
            last = exc
        time.sleep(5)
    raise ProductionVerificationFailure(
        f"Timed out waiting for {url}: status={last_status} last={last!r}"
    )


def _validate_api_contract(
    session: requests.Session,
    api_base: str,
    cfb_path: str,
) -> dict[str, Any]:
    health_http, health = _request_json(session, api_base + "/health")
    if health.get("status") != "ok":
        raise ProductionVerificationFailure(f"Render health drift: {health}")
    if health.get("service") != "kyre-sports-api":
        raise ProductionVerificationFailure(f"Render service identity drift: {health}")

    root_http, root = _request_json(session, api_base + "/")
    if root.get("name") != "Kyre Sports API" or root.get("status") != "online":
        raise ProductionVerificationFailure(f"Render API root contract drift: {root}")

    odds_http, odds = _request_json(session, api_base + cfb_path)
    if int(odds.get("step") or 0) != 3:
        raise ProductionVerificationFailure("CFB odds endpoint step drift")
    if odds.get("schema_version") != "cfb_odds_v1":
        raise ProductionVerificationFailure("CFB odds schema drift")

    diagnostics = odds.get("diagnostics") or {}
    semantics = odds.get("market_semantics") or {}
    if diagnostics.get("synthetic_official_ids") is not False:
        raise ProductionVerificationFailure("CFB synthetic official IDs became enabled")
    if diagnostics.get("fuzzy_matching") is not False:
        raise ProductionVerificationFailure("CFB fuzzy matching became enabled")
    if float(semantics.get("projection_weight")) != 0.0:
        raise ProductionVerificationFailure("CFB market projection weight is not 0%")
    if semantics.get("market_context_only") is not True:
        raise ProductionVerificationFailure("CFB market is no longer context-only")
    if semantics.get("may_modify_projection") is not False:
        raise ProductionVerificationFailure("CFB market can modify projection")
    games = odds.get("games")
    if not isinstance(games, list):
        raise ProductionVerificationFailure("CFB odds games is not a list")

    return {
        "health_http": health_http,
        "root_http": root_http,
        "cfb_odds_http": odds_http,
        "cfb_game_count": len(games),
        "cfb_projection_weight": semantics.get("projection_weight"),
        "cfb_fuzzy_matching": diagnostics.get("fuzzy_matching"),
        "cfb_synthetic_official_ids": diagnostics.get("synthetic_official_ids"),
    }


def _body_has_forbidden_error(body: str) -> str | None:
    for marker in FORBIDDEN_ERROR_MARKERS:
        if marker in body:
            return marker
    return None


def _find_app_frame(page, timeout_seconds: float = 120.0):
    deadline = time.monotonic() + timeout_seconds
    last_scan: list[dict[str, Any]] = []

    while time.monotonic() < deadline:
        scans: list[dict[str, Any]] = []
        for index, frame in enumerate(page.frames):
            try:
                body = frame.locator("body").inner_text(timeout=7000)
            except Exception:
                body = ""
            try:
                combos = frame.get_by_role("combobox").count()
            except Exception:
                combos = 0

            scans.append(
                {
                    "index": index,
                    "url": frame.url,
                    "comboboxes": combos,
                    "body_start": body[:800],
                }
            )

            if "get this app back up" in body.casefold():
                wake = frame.get_by_text("Yes, get this app back up!", exact=False)
                if wake.count() > 0:
                    wake.click()
                    page.wait_for_timeout(10000)
                    continue

            if combos >= 1 and (
                "KYRE SPORTS AI" in body
                or "🏟️ Sport" in body
                or "Sport" in body
            ):
                return frame, scans

        last_scan = scans
        page.wait_for_timeout(3000)

    raise ProductionVerificationFailure(
        "Could not find production Streamlit app frame: "
        + json.dumps(last_scan, ensure_ascii=False)
    )


def _choose(page, frame, combo_index: int, value: str) -> None:
    combos = frame.get_by_role("combobox")
    if combos.count() <= combo_index:
        raise ProductionVerificationFailure(
            f"Expected combobox {combo_index}; found {combos.count()}"
        )
    combos.nth(combo_index).click()
    page.wait_for_timeout(250)
    page.keyboard.type(value)
    page.keyboard.press("Enter")
    page.wait_for_timeout(2200)


def _browser_verify(
    streamlit_url: str,
    artifact_dir: Path,
) -> dict[str, Any]:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1400})
        try:
            page.goto(
                streamlit_url.rstrip("/") + "/",
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, scans = _find_app_frame(page)

            body = frame.locator("body").inner_text()
            forbidden = _body_has_forbidden_error(body)
            if forbidden:
                raise ProductionVerificationFailure(
                    f"Production Streamlit runtime error marker: {forbidden}"
                )

            combo = frame.get_by_role("combobox").nth(0)
            if combo.count() == 0:
                raise ProductionVerificationFailure(
                    "Production sport selector is missing"
                )

            try:
                initial_sport_value = combo.input_value(timeout=3000)
            except Exception:
                try:
                    initial_sport_value = combo.inner_text(timeout=3000)
                except Exception:
                    initial_sport_value = ""

            _choose(page, frame, 0, CFB_SPORT)

            deadline = time.monotonic() + 45.0
            while time.monotonic() < deadline:
                if frame.get_by_role("combobox").count() >= 2:
                    break
                page.wait_for_timeout(1000)
            else:
                raise ProductionVerificationFailure(
                    "Production CFB route did not expose market selector"
                )

            _choose(page, frame, 1, CFB_MARKET)

            deadline = time.monotonic() + 90.0
            final_body = ""
            while time.monotonic() < deadline:
                final_body = frame.locator("body").inner_text()
                if CFB_REQUIRED_MARKERS[0] in final_body:
                    break
                page.wait_for_timeout(1500)
            else:
                raise ProductionVerificationFailure(
                    "Production CFB Clean Page V26 Step 9 marker did not appear"
                )

            missing_markers = [
                marker for marker in CFB_REQUIRED_MARKERS
                if marker not in final_body
            ]
            if missing_markers:
                raise ProductionVerificationFailure(
                    "Production CFB Step 9 marker drift: " + " | ".join(missing_markers)
                )

            forbidden = _body_has_forbidden_error(final_body)
            if forbidden:
                raise ProductionVerificationFailure(
                    f"Production CFB route runtime error marker: {forbidden}"
                )

            screenshot = artifact_dir / "production_browser_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            return {
                "initial_sport_value": initial_sport_value,
                "sport_option_inventory_verified_by": "branch-local DevSystem browser QA",
                "cfb_route": f"{CFB_SPORT} -> {CFB_MARKET}",
                "cfb_markers": list(CFB_REQUIRED_MARKERS),
                "app_frame_url": frame.url,
                "frame_scan_count": len(scans),
                "screenshot": str(screenshot),
            }
        except Exception:
            try:
                page.screenshot(
                    path=str(artifact_dir / "production_browser_failure.png"),
                    full_page=True,
                )
            except Exception:
                pass
            raise
        finally:
            browser.close()


def run(
    *,
    artifact_dir: str | Path = "artifacts/production-verification",
) -> dict[str, Any]:
    targets = _load_targets()
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    streamlit_url = str(targets["streamlit"]["url"]).rstrip("/")
    api_base = str(targets["render_api"]["url"]).rstrip("/")
    cfb_path = str(targets["contracts"]["cfb_odds_path"])

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": "KyreSportsAI-DevSystem-ProductionVerify/1.0",
            "Cache-Control": "no-cache",
        }
    )

    streamlit_health_http = _wait_http_200(
        session,
        streamlit_url + str(targets["streamlit"]["health_path"]),
        timeout_seconds=420,
    )
    streamlit_root_http = _wait_http_200(
        session,
        streamlit_url + "/",
        timeout_seconds=420,
        expect_text="streamlit",
    )
    api_health_http = _wait_http_200(
        session,
        api_base + str(targets["render_api"]["health_path"]),
        timeout_seconds=420,
    )

    api = _validate_api_contract(session, api_base, cfb_path)
    browser = _browser_verify(streamlit_url, artifacts)

    result = {
        "status": "GREEN",
        "streamlit_url": streamlit_url,
        "streamlit_root_http": streamlit_root_http,
        "streamlit_health_http": streamlit_health_http,
        "render_api_url": api_base,
        "render_api_health_http": api_health_http,
        "render_service_id": targets["render_api"]["service_id"],
        "render_source_branch": targets["render_api"]["source_branch"],
        "render_auto_deploy": targets["render_api"]["auto_deploy"],
        **api,
        **browser,
    }

    result_path = artifacts / "production_verification.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("DEVSYSTEM_PRODUCTION_VERIFICATION_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/production-verification",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(artifact_dir=args.artifact_dir)
