"""CFB Top Picks Step 5 final visual and public production verifier."""
from __future__ import annotations

import argparse
from pathlib import Path
import time
from urllib.parse import urlencode, urljoin

import requests
from playwright.sync_api import sync_playwright

from browser_qa_v1 import _find_app_frame

PUBLIC_URL = "https://pickvault.streamlit.app"
ROOT = '[data-testid="cfb-top-picks-step5-root"][data-cfb-top-picks-visual="v5"]'
CARD = 'article[data-testid^="cfb-top-picks-card-"]'
OPEN_LINK = 'a[data-testid^="cfb-top-picks-open-"]'
DETAIL = '[data-testid^="cfb-top-picks-detail-panel-"]'
WIDTHS = ((390, 844), (768, 1024), (1440, 1000))


def _route(base_url: str) -> str:
    params = {
        "ks_sport": "College Football",
        "ks_cfb_market": "Top Picks",
    }
    return base_url.rstrip("/") + "/?" + urlencode(params)


def _wait_http(base_url: str, timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = requests.get(base_url, timeout=7)
            if response.status_code < 500:
                return
        except Exception:
            pass
        time.sleep(1.5)
    raise AssertionError("CFB_TOP_PICKS_STEP5_BASE_NOT_READY")


def _body(page) -> str:
    values = []
    for frame in page.frames:
        try:
            values.append(frame.locator("body").inner_text(timeout=2500))
        except Exception:
            pass
    return "\n".join(values)


def _find(page, selector: str, timeout: float = 180.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = _body(page)
        if "Traceback" in body or "TypeError" in body or "SyntaxError" in body:
            raise AssertionError("CFB_TOP_PICKS_STEP5_RUNTIME_ERROR:" + body[:5000])
        for frame in page.frames:
            try:
                locator = frame.locator(selector)
                if locator.count() >= 1:
                    return frame, locator.first
            except Exception:
                pass
        page.wait_for_timeout(500)
    raise AssertionError("CFB_TOP_PICKS_STEP5_SELECTOR_NOT_READY:" + selector)


def _wait_for_deployed_v5(page, base_url: str, timeout: float = 600.0):
    deadline = time.monotonic() + timeout
    route = _route(base_url)
    last_body = ""
    while time.monotonic() < deadline:
        try:
            page.goto(route, wait_until="domcontentloaded", timeout=120000)
            frame, root = _find(page, ROOT, timeout=45.0)
            return frame, root
        except Exception:
            last_body = _body(page)
            page.wait_for_timeout(6000)
    raise AssertionError("CFB_TOP_PICKS_STEP5_PUBLIC_DEPLOY_NOT_ACTIVE:" + last_body[:5000])


def _assert_no_overflow(frame) -> dict:
    dims = frame.locator("body").evaluate(
        """e => ({
            bodyScroll:e.scrollWidth,
            bodyClient:e.clientWidth,
            docScroll:document.documentElement.scrollWidth,
            viewport:window.innerWidth
        })"""
    )
    assert dims["bodyScroll"] <= dims["viewport"] + 2, dims
    assert dims["docScroll"] <= dims["viewport"] + 2, dims
    return dims


def _assert_cards_inside_viewport(frame, width: int) -> None:
    cards = frame.locator(CARD)
    assert cards.count() == 10, cards.count()
    for i in range(cards.count()):
        box = cards.nth(i).bounding_box()
        if box is None:
            continue
        assert box["x"] >= -2, (width, i, box)
        assert box["x"] + box["width"] <= width + 2, (width, i, box)


def _certify_board(page, base_url: str, width: int, height: int, artifacts: Path, public: bool) -> str:
    page.set_viewport_size({"width": width, "height": height})
    if public and width == WIDTHS[0][0]:
        frame, root = _wait_for_deployed_v5(page, base_url)
    else:
        page.goto(_route(base_url), wait_until="domcontentloaded", timeout=120000)
        frame, root = _find(page, ROOT, timeout=180.0)

    body = frame.locator("body").inner_text(timeout=5000)
    for marker in (
        "Top Picks",
        "10 Best Daily College Football Picks",
        "Tap a matchup for Why • History • Benefits",
    ):
        assert marker in body, (width, marker)

    market_tabs = root.locator('[data-testid="cfb-top-picks-market-tabs"]')
    assert market_tabs.count() == 1, (width, market_tabs.count())
    market_tab_text = market_tabs.inner_text(timeout=5000)
    for marker in ("Moneyline", "Spread", "Over/Under"):
        assert marker in market_tab_text, (width, marker, market_tab_text)

    assert root.locator(CARD).count() == 10
    links = root.locator(OPEN_LINK)
    assert links.count() == 10
    _assert_no_overflow(frame)
    _assert_cards_inside_viewport(frame, width)

    artifacts.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=str(artifacts / f"cfb_top_picks_step5_{width}_green.png"),
        full_page=True,
    )
    href = links.first.get_attribute("href") or ""
    assert "top_pick_detail=" in href
    print(f"CFB_TOP_PICKS_STEP5_{width}_GREEN")
    return urljoin(_route(base_url), href)


def _certify_detail(page, detail_url: str, artifacts: Path) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(detail_url, wait_until="domcontentloaded", timeout=120000)
    frame, _ = _find(page, DETAIL, timeout=180.0)

    markers = ("Why This Pick", "Actual Matchup History", "Benefits")
    deadline = time.monotonic() + 180.0
    panel = None
    body = ""

    while time.monotonic() < deadline:
        root = frame.locator(ROOT)
        panels = frame.locator(DETAIL)
        if root.count() == 1 and root.locator(CARD).count() == 10 and panels.count() >= 1:
            for index in range(panels.count()):
                candidate = panels.nth(index)
                try:
                    candidate_body = candidate.inner_text(timeout=2500)
                except Exception:
                    continue
                candidate_fold = candidate_body.casefold()
                if all(marker.casefold() in candidate_fold for marker in markers):
                    panel = candidate
                    body = candidate_body
                    break
        if panel is not None:
            break

        full_body = _body(page)
        if "Traceback" in full_body or "TypeError" in full_body or "SyntaxError" in full_body:
            raise AssertionError(
                "CFB_TOP_PICKS_STEP5_DETAIL_RUNTIME_ERROR:" + full_body[:5000]
            )
        page.wait_for_timeout(500)

    if panel is None:
        raise AssertionError(
            "CFB_TOP_PICKS_STEP5_DETAIL_TEXT_NOT_READY:"
            + repr({"required": markers, "last_body": body[:2000]})
        )

    root = frame.locator(ROOT)
    assert root.count() == 1
    assert root.locator(CARD).count() == 10
    assert frame.locator('details.tp4-details[data-expanded="true"]').count() == 1
    _assert_no_overflow(frame)
    page.screenshot(
        path=str(artifacts / "cfb_top_picks_step5_390_detail_green.png"),
        full_page=True,
    )
    print("CFB_TOP_PICKS_STEP5_DETAIL_GREEN")

def run(*, base_url: str, mode: str, artifact_dir: str | Path) -> None:
    public = mode == "public"
    _wait_http(base_url)
    artifacts = Path(artifact_dir)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 390, "height": 844})
        try:
            detail_url = ""
            for width, height in WIDTHS:
                current_detail = _certify_board(
                    page, base_url, width, height, artifacts, public
                )
                if width == 390:
                    detail_url = current_detail
            _certify_detail(page, detail_url, artifacts)
        finally:
            browser.close()

    if public:
        print("CFB_TOP_PICKS_STEP5_PUBLIC_PRODUCTION_GREEN")
        print("CFB_TOP_PICKS_STEPS1_5_FROZEN_GREEN")
    else:
        print("CFB_TOP_PICKS_STEP5_BRANCH_VISUAL_GREEN")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--mode", choices=("branch", "public"), required=True)
    parser.add_argument("--artifact-dir", required=True)
    args = parser.parse_args()
    run(base_url=args.base_url, mode=args.mode, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
