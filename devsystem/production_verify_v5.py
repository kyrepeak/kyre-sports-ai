"""DevSystem production verification V5 — real browser V163 persistence proof.

Streamlit Community Cloud hosts the app inside a /~/+ iframe. V163 game-card
navigation must therefore promote the selected official ESPN event_id to the
TOP-LEVEL browser URL, not merely the embedded app frame. This verifier proves
that real production behavior by switching games, checking the selected card,
hard-refreshing, and requiring the same event to survive.

Frozen V3 production proof and V4 V163 surface requirements are preserved.
No projection/model behavior is changed and no gate is weakened.
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
    from devsystem import production_verify_v3 as frozen_v3
    from devsystem import production_verify_v4 as v4
except ModuleNotFoundError:  # direct execution
    import production_verify_v1 as base
    import production_verify_v3 as frozen_v3
    import production_verify_v4 as v4

SUPERSEDES_VERIFIER = "devsystem.production_verify_v4"
FROZEN_PRODUCTION_BASE = "devsystem.production_verify_v3"
EXPECTED_ROUTER = v4.EXPECTED_ROUTER
GAME_TOTAL_REQUIRED_HEARTBEAT = v4.GAME_TOTAL_REQUIRED_HEARTBEAT
GAME_SELECTOR_REQUIRED_TEXT = v4.GAME_SELECTOR_REQUIRED_TEXT
EVENT_QUERY_KEY = v4.EVENT_QUERY_KEY
DATE_QUERY_KEY = v4.DATE_QUERY_KEY
ROUTE_QUERY_SPORT = v4.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = v4.ROUTE_QUERY_MARKET
CFB_SPORT = v4.CFB_SPORT
GAME_TOTAL_MARKET = v4.GAME_TOTAL_MARKET
CERT_DATE = v4.CERT_DATE
ProductionVerificationFailure = base.ProductionVerificationFailure


def _event_from_url(url: str) -> str:
    parsed = parse_qs(urlparse(str(url or "")).query)
    return str((parsed.get(EVENT_QUERY_KEY) or [""])[-1] or "").strip()


def _scan_v163_frame(page):
    scans: list[dict[str, Any]] = []
    for index, frame in enumerate(page.frames):
        try:
            body = frame.locator("body").inner_text(timeout=5000)
        except Exception:
            body = ""
        scans.append({"index": index, "url": frame.url, "body_start": body[:500]})
        if (
            GAME_TOTAL_REQUIRED_HEARTBEAT in body
            and GAME_SELECTOR_REQUIRED_TEXT in body
        ):
            return frame, body, scans
    return None, "", scans


def _find_v163_frame(page, timeout_seconds: float = 120.0):
    deadline = time.monotonic() + timeout_seconds
    last_scans: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        frame, body, scans = _scan_v163_frame(page)
        last_scans = scans
        if frame is not None:
            return frame, body, scans
        page.wait_for_timeout(750)
    raise ProductionVerificationFailure(
        "stale Streamlit Game Total V163 deployment: active V163 app frame not found; "
        + json.dumps(last_scans, ensure_ascii=False)
    )


def _selected_link_event(frame) -> str:
    selected = frame.locator(
        '[data-testid="gt163-game-strip"] '
        'button.gt163-game-link[aria-current="true"]'
    )
    if selected.count() != 1:
        raise ProductionVerificationFailure(
            "V163 production selector did not expose exactly one selected game card"
        )
    return str(selected.first.get_attribute("data-event-id") or "").strip()


def _switch_target(frame):
    links = frame.locator('[data-testid="gt163-game-strip"] button.gt163-game-link')
    count = links.count()
    if count < 2:
        raise ProductionVerificationFailure(
            f"V163 production selector needs at least two verified games; got {count}"
        )
    current = _selected_link_event(frame)
    for index in range(count):
        candidate = links.nth(index)
        event_id = str(candidate.get_attribute("data-event-id") or "").strip()
        if event_id and event_id != current:
            return candidate, event_id, count
    raise ProductionVerificationFailure(
        "V163 production selector had no second official ESPN event to switch to"
    )


def _wait_for_top_level_selection(
    page,
    expected_event: str,
    *,
    timeout_seconds: float = 120.0,
):
    deadline = time.monotonic() + timeout_seconds
    last_scans: list[dict[str, Any]] = []
    last_selected = ""
    while time.monotonic() < deadline:
        frame, body, scans = _scan_v163_frame(page)
        last_scans = scans
        if frame is not None:
            try:
                last_selected = _selected_link_event(frame)
            except Exception:
                last_selected = ""
            outer_event = _event_from_url(page.url)
            if outer_event == expected_event and last_selected == expected_event:
                return frame, body, scans
        page.wait_for_timeout(750)
    raise ProductionVerificationFailure(
        "V163 selected game did not persist at top-level browser URL: "
        f"expected={expected_event!r} outer={_event_from_url(page.url)!r} "
        f"selected={last_selected!r} url={page.url!r} scans="
        + json.dumps(last_scans, ensure_ascii=False)
    )


def _browser_verify_v163_selector(
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
            frame, body, initial_scans = _find_v163_frame(page)
            v4._assert_v163_surface(body)
            forbidden = base._body_has_forbidden_error(body)
            if forbidden:
                raise ProductionVerificationFailure(
                    f"Production Game Total V163 runtime error marker: {forbidden}"
                )

            target, target_event, button_count = _switch_target(frame)
            form = target.locator("xpath=ancestor::form[1]")
            if form.count() != 1:
                raise ProductionVerificationFailure(
                    "V163 game card is not wrapped in exactly one persistence form"
                )
            action = str(form.get_attribute("action") or "")
            method = str(form.get_attribute("method") or "").casefold()
            target_scope = str(form.get_attribute("target") or "")
            hidden_event = form.locator(f'input[name="{EVENT_QUERY_KEY}"]')
            hidden_event_value = (
                str(hidden_event.first.get_attribute("value") or "")
                if hidden_event.count() == 1
                else ""
            )
            if (
                action != "/"
                or method != "get"
                or target_scope != "_top"
                or hidden_event_value != target_event
            ):
                raise ProductionVerificationFailure(
                    "V163 game form is not top-level persistence safe: "
                    f"action={action!r} method={method!r} target={target_scope!r} "
                    f"hidden_event={hidden_event_value!r} expected={target_event!r}"
                )

            target.click(timeout=30000)
            switched_frame, switched_body, click_scans = _wait_for_top_level_selection(
                page,
                target_event,
            )
            v4._assert_v163_surface(switched_body)
            if _event_from_url(page.url) != target_event:
                raise ProductionVerificationFailure(
                    "V163 switch did not write official ESPN event_id to browser URL"
                )

            page.reload(wait_until="domcontentloaded", timeout=120000)
            reload_frame, reload_body, reload_scans = _wait_for_top_level_selection(
                page,
                target_event,
            )
            v4._assert_v163_surface(reload_body)
            reloaded_event = _selected_link_event(reload_frame)
            if reloaded_event != target_event:
                raise ProductionVerificationFailure(
                    "V163 selected ESPN event_id did not survive hard refresh"
                )

            evidence = v4._build_v163_evidence(
                expected_commit=expected_commit,
                event_id=target_event,
            )
            screenshot = artifact_dir / "production_game_total_v163_v5_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            return {
                **evidence,
                "game_total_route": f"{CFB_SPORT} -> {GAME_TOTAL_MARKET}",
                "certification_date": CERT_DATE,
                "game_button_count": button_count,
                "clicked_event_id": target_event,
                "reloaded_event_id": reloaded_event,
                "outer_wrapper_url": page.url,
                "game_total_app_frame_url": reload_frame.url,
                "initial_frame_scan_count": len(initial_scans),
                "click_frame_scan_count": len(click_scans),
                "reload_frame_scan_count": len(reload_scans),
                "top_level_event_persistence_verified": True,
                "hard_refresh_persistence_verified": True,
                "game_total_v163_screenshot": str(screenshot),
            }
        except Exception:
            try:
                page.screenshot(
                    path=str(
                        artifact_dir / "production_game_total_v163_v5_failure.png"
                    ),
                    full_page=True,
                )
            except Exception:
                pass
            raise
        finally:
            browser.close()


def run(
    *,
    artifact_dir: str | Path = "artifacts/production-verification-v5",
) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    result = dict(frozen_v3.run(artifact_dir=artifacts))

    targets = base._load_targets()
    streamlit_url = str(targets["streamlit"]["url"]).rstrip("/")
    expected_commit = str(os.environ.get("GITHUB_SHA") or "unknown")
    v163 = _browser_verify_v163_selector(
        streamlit_url,
        artifacts,
        expected_commit=expected_commit,
    )
    result.update(v163)
    result["status"] = "GREEN"
    result["production_verifier"] = "V5"

    result_path = artifacts / "production_verification_v5.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("DEVSYSTEM_PRODUCTION_VERIFICATION_V5_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/production-verification-v5",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(artifact_dir=args.artifact_dir)
