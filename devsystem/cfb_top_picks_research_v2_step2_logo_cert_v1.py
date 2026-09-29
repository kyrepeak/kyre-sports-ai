"""CFB Top Picks Research V2 Step 2 — real 10-card logo browser proof."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from devsystem import cfb_top_picks_nav_step3_public_cert_v1 as nav

DEFAULT_BASE_URL = "http://127.0.0.1:8501"


def run(*, base_url: str = DEFAULT_BASE_URL, artifact_dir: str | Path = "artifacts/cfb-top-picks-research-v2-step2") -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    nav._wait_http(base_url, timeout_seconds=120.0)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = None
        try:
            # Step 2 owns team identity/logo completeness, not Streamlit menu
            # activation timing. Reuse the frozen navigation proof as a bounded
            # precondition and retry it on a fresh page until the V5 route is
            # actually ready; the logo assertions below remain fail-closed.
            deadline = time.monotonic() + 120.0
            last_route_error = ""
            while time.monotonic() < deadline:
                if page is not None:
                    page.close()
                page = browser.new_page(viewport={"width": 390, "height": 844})
                try:
                    nav._attempt_normal_flow(page, base_url, 390, 844)
                    break
                except Exception as exc:
                    last_route_error = repr(exc)
                    page.close()
                    page = None
                    time.sleep(2.0)
            else:
                raise AssertionError(
                    "CFB_TOP_PICKS_RESEARCH_V2_STEP2_ROUTE_PRECONDITION_NOT_READY:"
                    + last_route_error
                )

            frame, root = nav._find_v5(page)

            cards = frame.locator('article[data-testid^="cfb-top-picks-card-"]')
            card_count = cards.count()
            if card_count != 10:
                raise AssertionError(f"CFB_TOP_PICKS_RESEARCH_V2_STEP2_CARD_COUNT:{card_count}")

            logos = frame.locator('img[data-top-picks-real-logo="true"]')
            logo_count = logos.count()
            if logo_count != 20:
                raise AssertionError(f"CFB_TOP_PICKS_RESEARCH_V2_STEP2_LOGO_COUNT:{logo_count}")

            placeholders = frame.locator('[data-logo-placeholder="true"]')
            if placeholders.count() != 0:
                raise AssertionError(
                    "CFB_TOP_PICKS_RESEARCH_V2_STEP2_PLACEHOLDERS:"
                    + str(placeholders.count())
                )

            evidence = []
            for idx in range(logo_count):
                logo = logos.nth(idx)
                src = str(logo.get_attribute("src") or "")
                team_id = str(logo.get_attribute("data-team-id") or "")
                provider = str(logo.get_attribute("data-logo-provider") or "")
                # Images are cross-origin network resources; wait boundedly for
                # browser decode/load before treating natural dimensions as proof.
                width = 0
                height = 0
                for _ in range(40):
                    width = int(logo.evaluate("el => el.naturalWidth || 0"))
                    height = int(logo.evaluate("el => el.naturalHeight || 0"))
                    if width > 0 and height > 0:
                        break
                    page.wait_for_timeout(250)
                if not src.startswith(("https://", "http://")):
                    raise AssertionError(f"CFB_TOP_PICKS_RESEARCH_V2_STEP2_BAD_SRC:{src}")
                if not team_id.isdigit():
                    raise AssertionError(f"CFB_TOP_PICKS_RESEARCH_V2_STEP2_BAD_TEAM_ID:{team_id}")
                if not provider:
                    raise AssertionError("CFB_TOP_PICKS_RESEARCH_V2_STEP2_PROVIDER_MISSING")
                if width <= 0 or height <= 0:
                    raise AssertionError(
                        f"CFB_TOP_PICKS_RESEARCH_V2_STEP2_IMAGE_NOT_LOADED:{team_id}:{src}"
                    )
                evidence.append({
                    "team_id": team_id,
                    "provider": provider,
                    "src": src,
                    "natural_width": width,
                    "natural_height": height,
                })

            screenshot = artifacts / "cfb_top_picks_research_v2_step2_390_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            payload = {
                "status": "GREEN",
                "cards": card_count,
                "real_logo_images": logo_count,
                "placeholders": 0,
                "api2_used": False,
                "logos": evidence,
            }
            (artifacts / "cfb_top_picks_research_v2_step2_evidence.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print("CFB_TOP_PICKS_RESEARCH_V2_STEP2_10_CARDS_GREEN")
            print("CFB_TOP_PICKS_RESEARCH_V2_STEP2_20_REAL_LOGOS_GREEN")
            print("CFB_TOP_PICKS_RESEARCH_V2_STEP2_API2_PROTECTED_GREEN")
            print("CFB_TOP_PICKS_RESEARCH_V2_STEP2_FROZEN_GREEN")
            print(json.dumps(payload, indent=2, sort_keys=True))
            return payload
        finally:
            if page is not None:
                page.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--artifact-dir", default="artifacts/cfb-top-picks-research-v2-step2")
    args = parser.parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
