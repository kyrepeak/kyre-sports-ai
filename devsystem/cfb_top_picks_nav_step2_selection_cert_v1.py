"""CFB Top Picks navigation Step 2 — normal dropdown selection proof."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

from devsystem import browser_qa_v1 as base

CFB_SPORT = "College Football"
CFB_MARKET_LABEL = "🎯 CFB Market"
TOP_PICKS = "Top Picks"
EXPECTED_CFB_MARKETS = ("Moneyline", "Over/Under", "Game Total", "Top Picks")
V5_ROOT = '[data-testid="cfb-top-picks-step5-root"][data-cfb-top-picks-visual="v5"]'
V5_MARKER = "CFB_TOP_PICKS_STEP5_FINAL_VISUAL_ACTIVE"


def _body(page) -> str:
    values = []
    for frame in page.frames:
        try:
            values.append(frame.locator("body").inner_text(timeout=2500))
        except Exception:
            pass
    return "\n".join(values)


def _find_v5(page, timeout_seconds: float = 180.0):
    deadline = time.monotonic() + timeout_seconds
    last_body = ""
    while time.monotonic() < deadline:
        last_body = _body(page)
        forbidden = base._body_has_forbidden_error(last_body)
        if forbidden:
            raise AssertionError(
                f"CFB_TOP_PICKS_NAV_STEP2_RUNTIME_ERROR:{forbidden}:{last_body[:4000]}"
            )
        for frame in page.frames:
            try:
                root = frame.locator(V5_ROOT)
                if root.count() == 1:
                    return frame, root
            except Exception:
                pass
        page.wait_for_timeout(500)
    raise AssertionError(
        "CFB_TOP_PICKS_NAV_STEP2_V5_NOT_READY:" + last_body[:5000]
    )


def _market_options(page, frame) -> list[str]:
    combo = frame.get_by_role("combobox", name=CFB_MARKET_LABEL, exact=True)
    combo.wait_for(state="visible", timeout=45000)
    combo.click()
    options_locator = page.get_by_role("option")
    options_locator.first.wait_for(state="visible", timeout=10000)
    options = [
        value.strip()
        for value in options_locator.all_inner_texts()
        if value.strip()
    ]
    page.keyboard.press("Escape")
    return options


def _assert_top_picks_query(page) -> dict[str, list[str]]:
    parsed = parse_qs(urlparse(page.url).query)
    sport = (parsed.get("ks_sport") or [""])[-1]
    market = (parsed.get("ks_cfb_market") or [""])[-1]
    if sport != CFB_SPORT or market != TOP_PICKS:
        raise AssertionError(
            "CFB_TOP_PICKS_NAV_STEP2_QUERY_MISMATCH:"
            f"sport={sport!r};market={market!r};url={page.url!r}"
        )
    return parsed


def run(*, base_url: str, artifact_dir: str | Path) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    health = base._wait_for_health(base_url)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 390, "height": 844})
        try:
            # Exact user flow: open normal app, choose College Football,
            # then choose Top Picks from the visible CFB market dropdown.
            page.goto(
                base_url.rstrip("/") + "/",
                wait_until="domcontentloaded",
                timeout=120000,
            )
            frame, initial_scan = base._find_app_frame(page)
            base._choose(page, frame, 0, CFB_SPORT)

            frame, cfb_scan = base._find_app_frame(page)
            before_options = _market_options(page, frame)
            missing_before = [
                value for value in EXPECTED_CFB_MARKETS if value not in before_options
            ]
            if missing_before:
                raise AssertionError(
                    f"CFB_TOP_PICKS_NAV_STEP2_PRESELECT_OPTIONS_MISSING:{missing_before!r}"
                )

            combo = frame.get_by_role("combobox", name=CFB_MARKET_LABEL, exact=True)
            combo.click()
            page.get_by_role("option", name=TOP_PICKS, exact=True).click()

            v5_frame, root = _find_v5(page)
            root_text = root.inner_text(timeout=5000)
            full_body = v5_frame.locator("body").inner_text(timeout=5000)
            if V5_MARKER not in full_body:
                raise AssertionError("CFB_TOP_PICKS_NAV_STEP2_V5_MARKER_MISSING")
            for marker in ("Top Picks", "10 Best Daily College Football Picks"):
                if marker not in full_body:
                    raise AssertionError(
                        f"CFB_TOP_PICKS_NAV_STEP2_VISIBLE_MARKER_MISSING:{marker}"
                    )

            query = _assert_top_picks_query(page)
            after_options = _market_options(page, v5_frame)
            missing_after = [
                value for value in EXPECTED_CFB_MARKETS if value not in after_options
            ]
            if missing_after:
                raise AssertionError(
                    f"CFB_TOP_PICKS_NAV_STEP2_POSTSELECT_OPTIONS_MISSING:{missing_after!r}"
                )
            if after_options.count(TOP_PICKS) != 1:
                raise AssertionError(
                    "CFB_TOP_PICKS_NAV_STEP2_TOP_PICKS_DUPLICATED:"
                    + str(after_options.count(TOP_PICKS))
                )

            screenshot = artifacts / "cfb_top_picks_nav_step2_selection_green.png"
            page.screenshot(path=str(screenshot), full_page=True)

            result = {
                "status": "GREEN",
                "health": health,
                "viewport": {"width": 390, "height": 844},
                "flow": "normal app -> College Football -> Top Picks",
                "before_options": before_options,
                "after_options": after_options,
                "query": query,
                "v5_root_count": root.count(),
                "v5_marker": V5_MARKER,
                "root_text_start": root_text[:700],
                "initial_frame_scan": initial_scan,
                "cfb_frame_scan": cfb_scan,
                "screenshot": str(screenshot),
            }
            (artifacts / "cfb_top_picks_nav_step2_selection_evidence.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print("CFB_TOP_PICKS_NAV_STEP2_SELECTION_GREEN")
            print("CFB_TOP_PICKS_NAV_STEP2_V5_ROUTE_GREEN")
            print("CFB_TOP_PICKS_NAV_STEP2_EXISTING_CFB_MARKETS_PRESERVED_GREEN")
            print("CFB_TOP_PICKS_NAV_STEP2_FROZEN_GREEN")
            print(json.dumps(result, indent=2, sort_keys=True))
            return result
        finally:
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8501")
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/cfb-top-picks-nav-step2-selection",
    )
    args = parser.parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
