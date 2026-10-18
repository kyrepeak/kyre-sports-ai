"""Dedicated production certification for CFB Game Total Step 5.

Certifies Step 5 independently from frozen Steps 1-4 while reusing the exact
existing production Step 5 DOM assertion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from devsystem import production_verify_v164_logos as full
import cfb_game_total_step5_pace_v1 as step5_owner


GREEN_MARKER = "CFB_GAME_TOTAL_V181_STEP5_PRODUCTION_GREEN"


def verify_live_step5(
    streamlit_url: str,
    *,
    artifact_dir: str | Path = "artifacts/production-step5-v181",
) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    # Certify a current scheduled matchup whose verified SportsDataverse
    # evidence is stored in the same Step 5 cache. This keeps the production
    # target and the nonblocking evidence source locked together.
    snapshot = json.loads(
        step5_owner.STEP5_PBP_SNAPSHOT_PATH.read_text(encoding="utf-8")
    )
    cert_date = str(snapshot.get("certification_game_date") or "").strip()
    cert_event_id = str(snapshot.get("certification_event_id") or "").strip()
    if not cert_date or not cert_event_id.isdigit():
        raise full.ProductionVerificationV164Failure(
            "V186 Step 5 certification target is missing from the PBP cache"
        )

    query = urlencode(
        {
            full.v163.ROUTE_QUERY_SPORT: full.v163.CFB_SPORT,
            full.v163.ROUTE_QUERY_MARKET: full.v163.GAME_TOTAL_MARKET,
            full.v163.DATE_QUERY_KEY: cert_date,
            full.v163.EVENT_QUERY_KEY: cert_event_id,
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
                streamlit_url.rstrip("/") + "/?" + query,
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, body, scans = full._wait_for_v164_patch_deployment(page)

            if full.REQUIRED_STEP5_DEPLOYMENT_MARKER not in body:
                raise full.ProductionVerificationV164Failure(
                    "V181 did not observe the V178 Step 5 production heartbeat"
                )

            event_id = (
                full.v163._event_from_url(page.url)
                or full.v163._event_from_url(frame.url)
            )
            if event_id != cert_event_id:
                raise full.ProductionVerificationV164Failure(
                    "V186 scheduled certification event did not persist: "
                    f"expected={cert_event_id!r} actual={event_id!r} "
                    f"page_url={page.url!r} frame_url={frame.url!r}"
                )
            selected_date = cert_date

            step5 = full._assert_step5_pace(frame)
            if (
                step5.get("status") != "READY"
                or int(step5.get("pace_coverage") or 0) != 100
                or int(step5.get("tile_count") or 0) != 12
                or not step5.get("v168_step5_verified")
            ):
                raise full.ProductionVerificationV164Failure(
                    f"V181 Step 5 result incomplete: {step5!r}"
                )

            screenshot = artifacts / "production_step5_v181_green.png"
            page.screenshot(path=str(screenshot), full_page=True)

            result = {
                "status": "GREEN",
                "date": selected_date,
                "event_id": event_id,
                "v178_heartbeat": full.REQUIRED_STEP5_DEPLOYMENT_MARKER,
                "step5": step5,
                "frame_scan_count": len(scans),
                "screenshot": str(screenshot),
            }
            (artifacts / "production_step5_v181_evidence.json").write_text(
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
        default="artifacts/production-step5-v181",
    )
    args = parser.parse_args()
    result = verify_live_step5(
        args.streamlit_url,
        artifact_dir=args.artifact_dir,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    print(GREEN_MARKER)


if __name__ == "__main__":
    main()
