"""Focused browser proof for CFB Top Picks Step 1 shell."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from devsystem.browser_qa_v1 import _find_app_frame


REQUIRED = (
    "Top Picks",
    "10 Best Daily College Football Picks",
    "Moneyline",
    "Spread",
    "Over/Under",
)


def run(base_url: str, artifact_dir: str | Path) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    url = (
        base_url.rstrip("/")
        + "/?ks_sport=College+Football&ks_cfb_market=Top+Picks"
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1050})
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            frame, scans = _find_app_frame(page, timeout_seconds=90.0)
            # The live Step-3 ranking engine may still be building after the
            # Streamlit frame itself is ready. Wait for the frozen Step-1
            # shell marker instead of sampling the spinner body too early.
            frame.get_by_text("10 Best Daily College Football Picks", exact=False).wait_for(
                state="visible", timeout=120000
            )
            body = frame.locator("body").inner_text(timeout=5000)
            missing = [value for value in REQUIRED if value not in body]
            if missing:
                raise AssertionError(
                    f"Top Picks shell missing {missing!r}. Body={body[:4000]!r}"
                )
            screenshot = artifacts / "cfb_top_picks_step1_shell_green.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "status": "GREEN",
                "route": "College Football -> Top Picks",
                "url": url,
                "required_markers": list(REQUIRED),
                "frame_url": frame.url,
                "frame_scan_count": len(scans),
                "screenshot": str(screenshot),
            }
            (artifacts / "cfb_top_picks_step1_evidence.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print("CFB_TOP_PICKS_STEP1_BROWSER_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        finally:
            browser.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8501")
    p.add_argument("--artifact-dir", default="artifacts/cfb-top-picks-step1")
    args = p.parse_args()
    run(args.base_url, args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
