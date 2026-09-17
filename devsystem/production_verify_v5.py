"""DevSystem production verification V5 — Streamlit Cloud frame-aware V163 proof.

V4's V163 proof reads the top-level browser URL. Streamlit Community Cloud
hosts the app inside a /~/+ iframe, so st.query_params can persist the selected
ESPN event_id on the app frame URL while the outer wrapper URL remains unchanged.

V5 keeps the frozen V3 production proof, preserves every V4 V163 surface check,
then reads the event query from the actual matched V163 app frame first and
cross-checks it against the selected game card. No projection/model behavior is
changed and the production gate is not weakened.
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


def _event_from_candidates(*urls: str) -> str:
    for url in urls:
        event_id = _event_from_url(url)
        if event_id:
            return event_id
    return ""


def _selected_link_event(frame) -> str:
    selected = frame.locator(
        '[data-testid="gt163-game-strip"] '
        'a.gt163-game-link[aria-current="true"]'
    )
    if selected.count() != 1:
        raise ProductionVerificationFailure(
            "V163 production selector did not expose exactly one selected game card"
        )
    return str(selected.first.get_attribute("data-event-id") or "").strip()


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
            deadline = time.monotonic() + 120.0
            final_body = ""
            selected_event = ""
            matched_frame = None
            scans: list[dict[str, Any]] = []
            while time.monotonic() < deadline:
                scans = []
                matched_frame = None
                for index, frame in enumerate(page.frames):
                    try:
                        body = frame.locator("body").inner_text(timeout=5000)
                    except Exception:
                        body = ""
                    scans.append(
                        {"index": index, "url": frame.url, "body_start": body[:500]}
                    )
                    if (
                        GAME_TOTAL_REQUIRED_HEARTBEAT in body
                        and GAME_SELECTOR_REQUIRED_TEXT in body
                    ):
                        final_body = body
                        matched_frame = frame
                        break

                if matched_frame is not None:
                    selected_event = _event_from_candidates(
                        matched_frame.url,
                        page.url,
                    )
                    if selected_event:
                        break
                page.wait_for_timeout(1000)

            v4._assert_v163_surface(final_body)
            if matched_frame is None:
                raise ProductionVerificationFailure(
                    "stale Streamlit Game Total V163 deployment: active V163 app frame not found"
                )
            forbidden = base._body_has_forbidden_error(final_body)
            if forbidden:
                raise ProductionVerificationFailure(
                    f"Production Game Total V163 runtime error marker: {forbidden}"
                )

            evidence = v4._build_v163_evidence(
                expected_commit=expected_commit,
                event_id=selected_event,
            )
            selected_card_event = _selected_link_event(matched_frame)
            if selected_card_event != selected_event:
                raise ProductionVerificationFailure(
                    "V163 persisted ESPN event_id does not match the selected game card: "
                    f"query={selected_event!r} card={selected_card_event!r}"
                )

            screenshot = artifact_dir / "production_game_total_v163_v5_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            return {
                **evidence,
                "game_total_route": f"{CFB_SPORT} -> {GAME_TOTAL_MARKET}",
                "certification_date": CERT_DATE,
                "outer_wrapper_url": page.url,
                "game_total_app_frame_url": matched_frame.url,
                "game_total_frame_scan_count": len(scans),
                "selected_card_event_id": selected_card_event,
                "streamlit_wrapper_aware_event_proof": True,
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

    # Preserve the complete frozen V3 Render/API/Streamlit proof. V5 replaces
    # only V4's wrapper-unaware event URL read with a stricter frame-aware proof.
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
