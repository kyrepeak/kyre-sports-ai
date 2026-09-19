"""Dedicated production certification for CFB Game Total Step 6.

Certifies the V184 Scoring Creation surface independently from frozen Steps
1-5. The verifier follows the current live Game Total selector rather than a
hard-coded historical event, waits for the V184 DOM, and requires the complete
READY / 100% / 12-of-12 contract.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.sync_api import sync_playwright

from devsystem import production_verify_v164_logos as full


GREEN_MARKER = "CFB_GAME_TOTAL_V184_STEP6_PRODUCTION_GREEN"
STEP6_MARKER = "CFB_GAME_TOTAL_STEP6_SCORING_CREATION_ACTIVE"
STEP6_DEPLOYMENT_MARKER = "CFB_GAME_TOTAL_STEP6_V184_DEPLOYMENT_ACTIVE"
STEP6_ROOT_SELECTOR = (
    'details.gt184-step6[data-testid="gt157-step-6"]'
    f'[data-step6-marker="{STEP6_MARKER}"]'
    f'[data-step6-deployment-marker="{STEP6_DEPLOYMENT_MARKER}"]'
)


def _wait_for_live_step6(page, timeout_seconds: float = 300.0):
    deadline = time.monotonic() + timeout_seconds
    last_body = ""
    last_error = ""

    while time.monotonic() < deadline:
        try:
            frame, body, scans = full._wait_for_v164_patch_deployment(page)
            last_body = body
            root = frame.locator(STEP6_ROOT_SELECTOR).last
            if root.count() > 0:
                root.wait_for(state="attached", timeout=5000)
                return frame, root, body, scans
            last_error = "V184 Step 6 root not live yet"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"[:500]

        page.wait_for_timeout(5000)
        page.reload(wait_until="domcontentloaded", timeout=120000)

    raise full.ProductionVerificationV164Failure(
        "V184 Step 6 production surface did not become live: "
        f"last_error={last_error!r} body_start={last_body[:3000]!r}"
    )


def _assert_step6(root) -> dict:
    marker = str(root.get_attribute("data-step6-marker") or "").strip()
    deployment_marker = str(
        root.get_attribute("data-step6-deployment-marker") or ""
    ).strip()
    state = str(root.get_attribute("data-step6-state") or "").strip()
    coverage = str(root.get_attribute("data-step6-coverage") or "").strip()
    ready_attr = str(root.get_attribute("data-step6-ready-tiles") or "").strip()

    tiles = root.locator('[data-testid="gt184-step6-stat-tile"]')
    tile_count = tiles.count()
    ready_tiles = root.locator(
        '[data-testid="gt184-step6-stat-tile"][data-ready="true"]'
    ).count()
    body_text = root.inner_text(timeout=10000)

    if marker != STEP6_MARKER:
        raise full.ProductionVerificationV164Failure(
            f"Step 6 marker mismatch: expected={STEP6_MARKER!r} actual={marker!r}"
        )
    if deployment_marker != STEP6_DEPLOYMENT_MARKER:
        raise full.ProductionVerificationV164Failure(
            "Step 6 deployment marker mismatch: "
            f"expected={STEP6_DEPLOYMENT_MARKER!r} actual={deployment_marker!r}"
        )
    if state != "READY":
        raise full.ProductionVerificationV164Failure(
            f"Step 6 state is not READY: {state!r}"
        )
    if coverage != "100":
        raise full.ProductionVerificationV164Failure(
            f"Step 6 coverage is not 100: {coverage!r}"
        )
    if ready_attr != "12" or tile_count != 12 or ready_tiles != 12:
        raise full.ProductionVerificationV164Failure(
            "Step 6 tile completeness failed: "
            f"attr={ready_attr!r} tiles={tile_count} ready_tiles={ready_tiles}"
        )
    if "DATA LIMITED" in body_text:
        raise full.ProductionVerificationV164Failure(
            "Step 6 READY surface still contains DATA LIMITED"
        )
    if "SPORTSBOOK INFLUENCE 0.0%" not in body_text:
        raise full.ProductionVerificationV164Failure(
            "Step 6 sportsbook-influence protection marker is missing"
        )
    if "PROJECTION MUTATION OFF" not in body_text:
        raise full.ProductionVerificationV164Failure(
            "Step 6 projection-mutation protection marker is missing"
        )

    return {
        "status": state,
        "coverage": int(coverage),
        "tile_count": tile_count,
        "ready_tiles": ready_tiles,
        "marker": marker,
        "deployment_marker": deployment_marker,
        "sportsbook_influence": 0.0,
        "projection_mutation": False,
    }


def verify_live_step6(
    streamlit_url: str,
    *,
    artifact_dir: str | Path = "artifacts/production-step6-v184",
) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    query = urlencode(
        {
            full.v163.ROUTE_QUERY_SPORT: full.v163.CFB_SPORT,
            full.v163.ROUTE_QUERY_MARKET: full.v163.GAME_TOTAL_MARKET,
        }
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1067, "height": 1800})
        try:
            page.goto(
                streamlit_url.rstrip("/") + "/?" + query,
                wait_until="domcontentloaded",
                timeout=120000,
            )

            frame, root, body, scans = _wait_for_live_step6(page)

            event_id = (
                full.v163._event_from_url(page.url)
                or full.v163._event_from_url(frame.url)
            )
            if not event_id or not str(event_id).isdigit():
                raise full.ProductionVerificationV164Failure(
                    "V184 current live Game Total event did not persist: "
                    f"page_url={page.url!r} frame_url={frame.url!r}"
                )

            routed_url = frame.url or page.url
            routed_query = parse_qs(urlparse(routed_url).query)
            date_values = routed_query.get(full.v163.DATE_QUERY_KEY) or []
            selected_date = str(date_values[-1] if date_values else "").strip()

            step6 = _assert_step6(root)

            screenshot = artifacts / "production_step6_v184_green.png"
            page.screenshot(path=str(screenshot), full_page=True)

            result = {
                "status": "GREEN",
                "date": selected_date,
                "event_id": str(event_id),
                "step6": step6,
                "frame_scan_count": len(scans),
                "screenshot": str(screenshot),
            }
            (artifacts / "production_step6_v184_evidence.json").write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return result
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    targets = full.base._load_targets()
    parser.add_argument(
        "--streamlit-url",
        default=str(targets["streamlit"]["url"]).rstrip("/"),
    )
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/production-step6-v184",
    )
    args = parser.parse_args()
    result = verify_live_step6(
        args.streamlit_url,
        artifact_dir=args.artifact_dir,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    print(GREEN_MARKER)


if __name__ == "__main__":
    main()
