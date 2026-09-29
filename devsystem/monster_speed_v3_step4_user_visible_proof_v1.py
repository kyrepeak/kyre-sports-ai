"""Monster Speed V3 Step 4 — real rendered responsive proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from devsystem import cfb_top_picks_nav_step3_public_cert_v1 as nav
from devsystem import user_visible_contract_v1 as user_contract


def run(*, base_url: str, artifact_dir: str | Path) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    nav._wait_http(base_url)

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 390, "height": 844})
        try:
            for width, height in nav.WIDTHS:
                result = nav._attempt_normal_flow(page, base_url, width, height)
                results.append(result)
                page.screenshot(
                    path=str(artifacts / f"monster_speed_v3_step4_{width}_green.png"),
                    full_page=True,
                )
                print(f"MONSTER_SPEED_V3_STEP4_{width}_USER_VISIBLE_GREEN")
        finally:
            browser.close()

    suite = user_contract.certify_responsive_suite(
        nav.TOP_PICKS_USER_CONTRACT,
        [item["user_visible_contract"] for item in results],
    )
    payload = {
        "status": "GREEN",
        "flow": "normal app -> College Football -> Top Picks",
        "contract": suite,
        "results": results,
    }
    (artifacts / "monster_speed_v3_step4_user_visible_evidence.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("MONSTER_SPEED_V3_STEP4_USER_VISIBLE_CONTRACT_GREEN")
    print("MONSTER_SPEED_V3_STEP4_FROZEN_GREEN")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8501")
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/monster-speed-v3-step4",
    )
    args = parser.parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
