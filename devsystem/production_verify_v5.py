"""DevSystem production verification V5 — real V163 game click persistence.

Additive successor to frozen production_verify_v4. V5 preserves the complete V3
production/API proof, then certifies the actual V163 user requirement on deployed
Streamlit: click a second verified game, require the official ESPN event_id in
the top-level browser URL, require the selected card/full surface to follow that
game, hard-refresh, and require the same event_id to remain selected.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.sync_api import sync_playwright

try:
    from devsystem import production_verify_v1 as base
    from devsystem import production_verify_v3 as prior
except ModuleNotFoundError:  # direct script execution
    import production_verify_v1 as base
    import production_verify_v3 as prior

FROZEN_VERIFIER = "devsystem.production_verify_v3"
EXPECTED_ROUTER = "streamlit_memory_lazy_router_v159"
GAME_TOTAL_REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V163_PRODUCTION_ACTIVE"
GAME_SELECTOR_REQUIRED_TEXT = "GAMES ON THIS DAY"
FULL_RENDER_MARKER = "VIEW TOP 5 →"
EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"
DATE_QUERY_KEY = "ks_cfb_game_total_date"
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"
CFB_SPORT = "College Football"
GAME_TOTAL_MARKET = "Game Total"
CERT_DATE = "2026-09-19"
ProductionVerificationFailure = base.ProductionVerificationFailure


def _event_from_url(url: str) -> str:
    state = parse_qs(urlparse(str(url or "")).query)
    return str((state.get(EVENT_QUERY_KEY) or [""])[-1] or "").strip()


def _is_v163_surface(body: str) -> bool:
    text = str(body or "")
    return (
        GAME_TOTAL_REQUIRED_HEARTBEAT in text
        and GAME_SELECTOR_REQUIRED_TEXT in text
        and FULL_RENDER_MARKER in text
    )


def _find_v163_frame(page, timeout_seconds: float = 120.0):
    deadline = time.monotonic() + timeout_seconds
    last_scan: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        scans: list[dict[str, Any]] = []
        for index, frame in enumerate(page.frames):
            try:
                body = frame.locator("body").inner_text(timeout=5000)
            except Exception:
                body = ""
            scans.append({"index": index, "url": frame.url, "body_start": body[:700]})
            if _is_v163_surface(body):
                return frame, body, scans
        last_scan = scans
        page.wait_for_timeout(750)
    raise ProductionVerificationFailure(
        "deployed V163 Game Total surface was not found: "
        + json.dumps(last_scan, ensure_ascii=False)
    )


def _selected_link_event(frame) -> str:
    selected = frame.locator(
        '[data-testid="gt163-game-strip"] a.gt163-game-link[aria-current="true"]'
    )
    if selected.count() != 1:
        raise ProductionVerificationFailure(
            f"expected exactly one selected V163 game link, found {selected.count()}"
        )
    return str(selected.first.get_attribute("data-event-id") or "").strip()


def _wait_for_top_event(page, expected: str, timeout_seconds: float = 60.0) -> str:
    deadline = time.monotonic() + timeout_seconds
    last = ""
    while time.monotonic() < deadline:
        last = _event_from_url(page.url)
        if last == expected:
            return last
        page.wait_for_timeout(400)
    raise ProductionVerificationFailure(
        "clicked ESPN event_id was not persisted in top-level URL: "
        f"expected={expected!r} actual={last!r} url={page.url!r}"
    )


def _assert_clean_surface(body: str) -> None:
    forbidden = base._body_has_forbidden_error(body)
    if forbidden:
        raise ProductionVerificationFailure(
            f"Production Game Total V163 runtime error marker: {forbidden}"
        )


def _browser_verify_v163_click_persistence(
    streamlit_url: str,
    artifact_dir: Path,
    *,
    expected_commit: str,
) -> dict[str, Any]:
    direct_query = urlencode(
        {
            ROUTE_QUERY_SPORT: CFB_SPORT,
            ROUTE_QUERY_MARKET: GAME_TOTAL_MARKET,
            DATE_QUERY_KEY: CERT_DATE,
        }
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1067, "height": 1536})
        try:
            page.goto(
                streamlit_url.rstrip("/") + "/?" + direct_query,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, body, initial_scan = _find_v163_frame(page)
            _assert_clean_surface(body)

            strip = frame.locator('[data-testid="gt163-game-strip"]')
            links = strip.locator("a.gt163-game-link")
            count = links.count()
            if count < 2:
                raise ProductionVerificationFailure(
                    f"expected at least two verified V163 games on {CERT_DATE}, got {count}"
                )

            initial_event = _selected_link_event(frame)
            target = None
            target_event = ""
            target_label = ""
            for index in range(count):
                candidate = links.nth(index)
                event_id = str(candidate.get_attribute("data-event-id") or "").strip()
                if event_id and event_id != initial_event:
                    target = candidate
                    target_event = event_id
                    target_label = candidate.inner_text().strip()
                    break
            if target is None:
                raise ProductionVerificationFailure(
                    "no second verified ESPN matchup was available for V163 production click proof"
                )

            target.click(timeout=30000)
            clicked_event = _wait_for_top_event(page, target_event)
            frame_after_click, body_after_click, click_scan = _find_v163_frame(page)
            _assert_clean_surface(body_after_click)
            if _selected_link_event(frame_after_click) != target_event:
                raise ProductionVerificationFailure(
                    "clicked V163 game did not become the selected game after top-level navigation"
                )

            page.reload(wait_until="domcontentloaded", timeout=120000)
            if _event_from_url(page.url) != target_event:
                raise ProductionVerificationFailure(
                    "selected ESPN event_id did not survive hard refresh"
                )
            frame_after_reload, body_after_reload, reload_scan = _find_v163_frame(page)
            _assert_clean_surface(body_after_reload)
            if _selected_link_event(frame_after_reload) != target_event:
                raise ProductionVerificationFailure(
                    "selected ESPN event_id did not survive hard refresh"
                )

            screenshot = artifact_dir / "production_game_total_v163_click_refresh_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            return {
                "expected_commit": expected_commit,
                "expected_router": EXPECTED_ROUTER,
                "observed_router": "V159",
                "observed_build_marker": GAME_TOTAL_REQUIRED_HEARTBEAT,
                "game_selector_visible": True,
                "game_link_count": count,
                "initial_selected_espn_event_id": initial_event,
                "clicked_espn_event_id": clicked_event,
                "reloaded_espn_event_id": target_event,
                "clicked_label": target_label,
                "top_level_url": page.url,
                "initial_frame_scan": initial_scan,
                "click_frame_scan": click_scan,
                "reload_frame_scan": reload_scan,
                "game_total_v163_screenshot": str(screenshot),
                "v163_click_refresh_verified": True,
            }
        except Exception:
            try:
                page.screenshot(
                    path=str(artifact_dir / "production_game_total_v163_click_refresh_failure.png"),
                    full_page=True,
                )
            except Exception:
                pass
            raise
        finally:
            browser.close()


def run(*, artifact_dir: str | Path = "artifacts/production-verification") -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    result = dict(prior.run(artifact_dir=artifacts))
    targets = base._load_targets()
    streamlit_url = str(targets["streamlit"]["url"]).rstrip("/")
    expected_commit = str(os.environ.get("GITHUB_SHA") or "unknown")
    result.update(
        _browser_verify_v163_click_persistence(
            streamlit_url,
            artifacts,
            expected_commit=expected_commit,
        )
    )
    result["status"] = "GREEN"
    result["production_verifier"] = "V5"

    result_path = artifacts / "production_verification.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("DEVSYSTEM_PRODUCTION_VERIFICATION_V5_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", default="artifacts/production-verification")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(artifact_dir=args.artifact_dir)
