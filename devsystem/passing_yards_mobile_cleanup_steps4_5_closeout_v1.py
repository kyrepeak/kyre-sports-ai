"""Passing Yards mobile cleanup Steps 4-5 closeout certification.

Step 4: branch-local desktop visual closeout at 1024px and 1440px.
Step 5: one public-production final proof at phone/tablet/desktop widths.

This verifier is read-only with respect to product behavior.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import time
from urllib.parse import urlencode

import requests
from playwright.sync_api import sync_playwright

EXPECTED_DATE = "2026-09-24"
EXPECTED_MATCHUP = "Atlanta Falcons @ Green Bay Packers"
EXPECTED_QB = "Jordan Love"


def _route(base_url: str, *, detail: bool) -> str:
    params = {
        "ks_jump_sport": "NFL",
        "ks_jump_market": "Passing Yards",
        "ks_py_date": EXPECTED_DATE,
        "ks_py_matchup": EXPECTED_MATCHUP,
    }
    if detail:
        params["ks_qb_slot"] = "2"
    return base_url.rstrip("/") + "/?" + urlencode(params)


def _wait_http(base_url: str, timeout: float = 150.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if requests.get(base_url, timeout=5).status_code < 500:
                return
        except Exception:
            pass
        time.sleep(1.0)
    raise RuntimeError("PASSING_YARDS_STEPS4_5_BASE_NOT_READY")


def _body_text(page) -> str:
    out = []
    for frame in page.frames:
        try:
            out.append(frame.locator("body").inner_text(timeout=2500))
        except Exception:
            pass
    return "\n".join(out)


def _find(page, selector: str, timeout: float = 180.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = _body_text(page)
        if "TypeError" in body or "Traceback" in body:
            print(body[:50000])
            raise RuntimeError("PASSING_YARDS_STEPS4_5_RUNTIME_ERROR")
        for frame in page.frames:
            try:
                loc = frame.locator(selector)
                if loc.count() >= 1:
                    return frame, loc.first
            except Exception:
                pass
        page.wait_for_timeout(400)
    raise RuntimeError("PASSING_YARDS_STEPS4_5_SELECTOR_NOT_READY:" + selector)


def _assert_value_above_label(frame, tile_selector: str) -> None:
    tiles = frame.locator(tile_selector)
    assert tiles.count() >= 1, tile_selector
    checked = 0
    for i in range(min(tiles.count(), 10)):
        tile = tiles.nth(i)
        b = tile.locator("b").first
        span = tile.locator("span").first
        if b.count() != 1 or span.count() != 1:
            continue
        assert b.evaluate("e => getComputedStyle(e).display") == "block", (tile_selector, i, "value")
        assert span.evaluate("e => getComputedStyle(e).display") == "block", (tile_selector, i, "label")
        bb = b.bounding_box()
        sb = span.bounding_box()
        if bb and sb:
            assert sb["y"] >= bb["y"] + bb["height"] - 2, (tile_selector, i, bb, sb)
        checked += 1
    assert checked >= 1, tile_selector


def _assert_badge(locator, selector: str) -> None:
    assert locator.count() == 1, selector
    assert locator.evaluate("e => getComputedStyle(e).borderRadius") != "0px", selector
    box = locator.bounding_box()
    if box:
        assert box["width"] < 180 and box["height"] <= 44, (selector, box)


def _certify_width(page, base_url: str, width: int, height: int, artifact_dir: Path) -> None:
    page.set_viewport_size({"width": width, "height": height})

    # Surface 1: Game Center.
    page.goto(_route(base_url, detail=False), wait_until="domcontentloaded", timeout=120000)
    frame, marker = _find(page, '[data-passing-yards-mobile-cleanup-runtime="v70"]')
    assert marker.count() == 1
    _, center = _find(page, ".kpy15-center")
    assert center.count() == 1
    _assert_value_above_label(frame, ".kpy15-center .kpy15-metric")
    _assert_badge(frame.locator(".kpy15-center .kpy15-conf").first, ".kpy15-conf")

    # Surfaces 2-6: selected-QB Deep Evidence.
    page.goto(_route(base_url, detail=True), wait_until="domcontentloaded", timeout=120000)
    frame, root = _find(
        page,
        '[data-passing-yards-qb-detail="v59"][data-passing-yards-detail-cleanup="v69"]',
    )
    body = frame.locator("body").inner_text(timeout=5000)
    assert EXPECTED_QB in body
    assert "TypeError" not in body and "Traceback" not in body
    assert frame.locator('[data-passing-yards-mobile-cleanup-runtime="v70"]').count() == 1

    deep = root.locator('#ks-py-deep-evidence[data-passing-yards-deep-evidence="v67"]')
    assert deep.count() == 1
    assert deep.locator("[data-deep-evidence-kind]").count() == 5

    expected = {
        "recent": ".kpass30-profile",
        "opponent": ".kpy-defense",
        "pressure": ".kpy-pressure",
        "personnel": ".kpy-personnel",
        "environment": ".kpy-env",
    }
    for kind, selector in expected.items():
        card = deep.locator(f'[data-deep-evidence-kind="{kind}"]')
        assert card.count() == 1, kind
        assert card.locator(selector).count() == 1, (kind, selector)

    _assert_value_above_label(frame, "#ks-py-deep-evidence .kpass30-herostat")
    _assert_value_above_label(frame, "#ks-py-deep-evidence .kpy-dmetric")
    _assert_value_above_label(frame, "#ks-py-deep-evidence .kpy-xmetric")
    _assert_value_above_label(frame, "#ks-py-deep-evidence .kpy-imetric")
    _assert_value_above_label(frame, "#ks-py-deep-evidence .kpy-envmetric")

    envcell = deep.locator(".kpy-envcell").first
    assert envcell.count() == 1
    assert envcell.evaluate("e => getComputedStyle(e).display") == "flex"
    assert envcell.evaluate("e => getComputedStyle(e).flexDirection") == "column"

    for selector in (
        ".kpass30-state",
        ".kpy-grade",
        ".kpy-xgrade",
        ".kpy-ilabel",
        ".kpy-envlabel",
    ):
        _assert_badge(deep.locator(selector).first, selector)

    assert root.locator("[data-passing-yards-clean-detail]").count() == 4
    nav = root.locator('[data-passing-yards-category-nav="v62"]')
    assert nav.count() == 1
    assert nav.locator("a.ks-py62-category-link").count() == 6

    back_count = 0
    for candidate in page.frames:
        try:
            back_count += candidate.get_by_role("button", name="← Back to Quarterbacks", exact=True).count()
        except Exception:
            pass
    assert back_count >= 1

    dims = frame.locator("body").evaluate(
        """e => ({
            bodyScroll:e.scrollWidth,
            docScroll:document.documentElement.scrollWidth,
            viewport:window.innerWidth
        })"""
    )
    assert dims["bodyScroll"] <= dims["viewport"] + 2, dims
    assert dims["docScroll"] <= dims["viewport"] + 2, dims

    artifact_dir.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(artifact_dir / f"passing_yards_steps4_5_{width}_green.png"), full_page=True)
    print(f"PASSING_YARDS_MOBILE_CLEANUP_STEPS4_5_{width}_GREEN")


def run(*, base_url: str, mode: str, artifact_dir: str | Path) -> None:
    _wait_http(base_url)
    artifacts = Path(artifact_dir)
    widths = [(1024, 1366), (1440, 1000)] if mode == "desktop" else [
        (390, 844),
        (768, 1024),
        (1024, 1366),
        (1440, 1000),
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page(viewport={"width": widths[0][0], "height": widths[0][1]})
        try:
            for width, height in widths:
                _certify_width(page, base_url, width, height, artifacts)
        finally:
            browser.close()

    if mode == "desktop":
        print("PASSING_YARDS_MOBILE_CLEANUP_STEP4_DESKTOP_GREEN")
    else:
        print("PASSING_YARDS_MOBILE_CLEANUP_STEP5_PUBLIC_GREEN")
        print("PASSING_YARDS_MOBILE_CLEANUP_STEPS1_5_FROZEN_GREEN")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--mode", choices=("desktop", "public"), required=True)
    parser.add_argument("--artifact-dir", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(base_url=args.base_url, mode=args.mode, artifact_dir=args.artifact_dir)
