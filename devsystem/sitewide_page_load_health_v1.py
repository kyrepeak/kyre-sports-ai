"""Sitewide public page-load health audit V1.

Audits every user-facing Kyre Sports AI sport/market route without modifying
runtime/product code. Passing Yards is observed but remains protected from this
workstream.

Success proves:
- route jump resolves,
- first meaningful page render is present,
- selected sport/market state is visible,
- no common fatal runtime exception is rendered,
- the page survives 390/768/1440 viewport changes without root overflow.

This is a browser acceptance verifier, not model-quality or betting-math proof.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import Page, sync_playwright

PUBLIC_BASE_URL = "https://kyre-sports-ai.streamlit.app"

ROUTES = [
    # NFL
    ("NFL", "NFL", "Slate"),
    ("NFL", "NFL", "Moneyline"),
    ("NFL", "NFL", "Spread"),
    ("NFL", "NFL", "Game Total"),
    ("NFL", "NFL", "Passing Yards"),
    ("NFL", "NFL", "Rushing Yards"),
    ("NFL", "NFL", "Receiving Yards"),
    ("NFL", "NFL", "Receptions"),
    ("NFL", "NFL", "Passing TDs"),
    ("NFL", "NFL", "Anytime TD"),
    ("NFL", "NFL", "Daily Picks"),
    # College Football
    ("CFB", "College Football", "Moneyline"),
    ("CFB", "College Football", "Over/Under"),
    ("CFB", "College Football", "Game Total"),
    # MLB
    ("MLB", "MLB", "Slate"),
    ("MLB", "MLB", "1+ Hit"),
    ("MLB", "MLB", "2+ Hits"),
    ("MLB", "MLB", "Home Run"),
    ("MLB", "MLB", "Hits + Runs + RBIs"),
    ("MLB", "MLB", "Pitcher Strikeouts"),
    ("MLB", "MLB", "Matchup Explorer"),
    ("MLB", "MLB", "Daily Game Picks"),
    ("MLB", "MLB", "Moneyline"),
    ("MLB", "MLB", "Run Line"),
    ("MLB", "MLB", "Game Total"),
    ("MLB", "MLB", "Live Game"),
    # WNBA
    ("WNBA", "WNBA", "Points"),
    ("WNBA", "WNBA", "Rebounds"),
    ("WNBA", "WNBA", "Assists"),
    ("WNBA", "WNBA", "Rebounds + Assists"),
    ("WNBA", "WNBA", "PRA"),
    ("WNBA", "WNBA", "Spread"),
    ("WNBA", "WNBA", "Moneyline"),
    ("WNBA", "WNBA", "Game Total"),
    ("WNBA", "WNBA", "Daily Picks"),
]

SPECIAL_ROUTES = [("MLB", "MLB", "MLB Live Odds")]

EXPECTED_ROUTE_COUNT = 36
PROTECTED_ROUTE = ("NFL", "Passing Yards")

FATAL_MARKERS = (
    "Traceback (most recent call last)",
    "RecursionError:",
    "KeyError:",
    "TypeError:",
    "AttributeError:",
    "ModuleNotFoundError:",
    "This app has encountered an error",
    "Uncaught app exception",
)

WIDTHS = ((390, 844), (768, 1024), (1440, 1000))

# Route-specific identity aliases observed in real production surfaces. These
# prevent the verifier from requiring navigation-label wording to be repeated
# verbatim inside a page that has already rendered its certified owner.
ROUTE_RENDER_MARKERS = {
    ("CFB", "Over/Under"): ("CFB O/U", "CLEAN PAGE V39 ACTIVE"),
    ("CFB", "Game Total"): ("Game Total matchup", "CFB_GAME_TOTAL_"),
    ("MLB", "Matchup Explorer"): ("Find your matchup + hitter",),
    ("MLB", "Daily Game Picks"): ("Kyre Sports API connected", "FanDuel live market context"),
    ("WNBA", "Assists"): ("assist-rate", "Current roster + availability"),
    ("WNBA", "Rebounds + Assists"): ("R+A slate date", "R+A paired rows"),
}

SPORT_RENDER_MARKERS = {
    "NFL": ("NFL",),
    "CFB": ("College Football", "CFB"),
    "MLB": ("MLB",),
    "WNBA": ("WNBA",),
}

# Strong route-owned DOM markers. These are preferred over prose wording when
# a production page has a stable certified container/marker of its own.
ROUTE_DOM_MARKERS = {
    ("NFL", "Slate"): ".knfl-shell",
    ("NFL", "Moneyline"): ".kml9-page",
    ("CFB", "Game Total"): '[data-testid="gt233-sport-dropdown-nav"]',
    ("MLB", "Hits + Runs + RBIs"): ".hrr115-step-badge",
    ("MLB", "Matchup Explorer"): ".mx49-section",
}


@dataclass
class RouteResult:
    sport_code: str
    sport_label: str
    market: str
    smoke: str = "NOT_RUN"
    flow: str = "NOT_RUN"
    responsive: str = "NOT_RUN"
    protected: bool = False
    detail: str = ""
    first_render_seconds: float | None = None


def _all_frame_text(page: Page) -> str:
    chunks: list[str] = []
    for frame in page.frames:
        try:
            text = frame.locator("body").inner_text(timeout=1500)
        except Exception:
            continue
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def _fatal_marker(text: str) -> str | None:
    for marker in FATAL_MARKERS:
        if marker in text:
            return marker
    return None


def _route_url(base_url: str, sport_code: str, market: str) -> str:
    return base_url.rstrip("/") + "/?" + urlencode(
        {"ks_jump_sport": sport_code, "ks_jump_market": market}
    )


def _route_identity_visible(
    text: str, *, sport_code: str, sport_label: str, market: str
) -> bool:
    clean = " ".join(text.split())
    markers = ROUTE_RENDER_MARKERS.get((sport_code, market), (market,))
    sport_markers = SPORT_RENDER_MARKERS.get(sport_code, (sport_label, sport_code))
    return any(marker in clean for marker in markers) and any(
        marker in clean for marker in sport_markers
    )


def _route_dom_visible(page: Page, *, sport_code: str, market: str) -> bool:
    selector = ROUTE_DOM_MARKERS.get((sport_code, market))
    if not selector:
        return False
    for frame in page.frames:
        try:
            if frame.locator(selector).count() > 0:
                return True
        except Exception:
            pass
    return False


def _streamlit_busy(page: Page) -> bool:
    for frame in page.frames:
        try:
            stop = frame.get_by_role("button", name="Stop")
            if stop.count() > 0 and stop.first.is_visible():
                return True
        except Exception:
            pass
    return False


def _meaningful_route_visible(
    text: str, *, sport_code: str, sport_label: str, market: str
) -> bool:
    clean = " ".join(text.split())
    if "KYRE SPORTS AI" not in clean:
        return False
    if not _route_identity_visible(
        clean, sport_code=sport_code, sport_label=sport_label, market=market
    ):
        return False
    # Avoid accepting only the global shell / selectors.
    if len(clean) < 220:
        return False
    return True


def _wait_for_meaningful_route(
    page: Page,
    *,
    sport_code: str,
    sport_label: str,
    market: str,
    timeout: float = 45.0,
    require_idle: bool = True,
) -> tuple[str, float]:
    started = time.monotonic()
    deadline = started + timeout
    last = ""
    while time.monotonic() < deadline:
        last = _all_frame_text(page)
        fatal = _fatal_marker(last)
        if fatal:
            raise RuntimeError(f"FATAL_RENDER:{fatal}")
        route_ready = _route_dom_visible(page, sport_code=sport_code, market=market) or _meaningful_route_visible(
            last, sport_code=sport_code, sport_label=sport_label, market=market
        )
        if route_ready and (not require_idle or not _streamlit_busy(page)):
            return last, time.monotonic() - started
        time.sleep(0.35)
    sample = " ".join(last.split())[:700]
    raise RuntimeError(f"FIRST_MEANINGFUL_RENDER_NOT_READY:{sample}")


def _root_overflow(page: Page) -> tuple[bool, str]:
    worst = 0
    samples: list[str] = []
    for frame in page.frames:
        try:
            dims = frame.locator("html").evaluate(
                """e => ({
                    sw: document.documentElement.scrollWidth,
                    cw: document.documentElement.clientWidth,
                    bw: document.body ? document.body.scrollWidth : 0,
                    iw: window.innerWidth
                })"""
            )
        except Exception:
            continue
        sw = max(int(dims.get("sw") or 0), int(dims.get("bw") or 0))
        cw = max(int(dims.get("cw") or 0), int(dims.get("iw") or 0))
        delta = sw - cw
        worst = max(worst, delta)
        samples.append(f"{sw}/{cw}")
    # A few pixels can be browser rounding / scrollbars.
    return worst > 8, f"worst_delta={worst};frames={','.join(samples[:4])}"


def _audit_normal_route(
    page: Page,
    base_url: str,
    row: tuple[str, str, str],
    *,
    steps23_only: bool = False,
) -> RouteResult:
    sport_code, sport_label, market = row
    result = RouteResult(
        sport_code=sport_code,
        sport_label=sport_label,
        market=market,
        protected=(sport_code, market) == PROTECTED_ROUTE,
    )
    url = _route_url(base_url, sport_code, market)
    try:
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        text, seconds = _wait_for_meaningful_route(
            page,
            sport_code=sport_code,
            sport_label=sport_label,
            market=market,
            require_idle=not steps23_only,
        )
        result.first_render_seconds = round(seconds, 3)
        result.smoke = "GREEN"

        # User-flow proof: query/category jump must settle to real selected route,
        # not merely leave query params untouched or render only the global shell.
        fatal = _fatal_marker(text)
        if fatal:
            raise RuntimeError(f"FLOW_FATAL:{fatal}")
        if not (
            _route_dom_visible(page, sport_code=sport_code, market=market)
            or _route_identity_visible(
                text, sport_code=sport_code, sport_label=sport_label, market=market
            )
        ):
            raise RuntimeError("FLOW_SELECTED_ROUTE_IDENTITY_NOT_VISIBLE")
        result.flow = "GREEN"

        if steps23_only:
            result.responsive = "NOT_REQUIRED"
            if market == "2+ Hits" and "standalone 2+ Hits route remains unbuilt" in text:
                result.detail = "DEGRADED_PLACEHOLDER: route loads but standalone production model is intentionally unbuilt"
            elif result.protected:
                result.detail = "PROTECTED_PASSING_YARDS: observed only; no product mutation authorized here"
            return result

        for width, height in WIDTHS:
            page.set_viewport_size({"width": width, "height": height})
            time.sleep(0.25)
            current = _all_frame_text(page)
            fatal = _fatal_marker(current)
            if fatal:
                raise RuntimeError(f"RESPONSIVE_FATAL:{width}:{fatal}")
            overflow, detail = _root_overflow(page)
            if overflow:
                raise RuntimeError(f"ROOT_OVERFLOW:{width}:{detail}")
        result.responsive = "GREEN"

        if market == "2+ Hits" and "standalone 2+ Hits route remains unbuilt" in text:
            result.detail = "DEGRADED_PLACEHOLDER: route loads but standalone production model is intentionally unbuilt"
        elif result.protected:
            result.detail = "PROTECTED_PASSING_YARDS: observed only; no product mutation authorized here"
    except Exception as exc:
        message = f"{type(exc).__name__}:{exc}"
        result.detail = message[:1200]
        if result.smoke != "GREEN":
            result.smoke = "RED"
        elif result.flow != "GREEN":
            result.flow = "RED"
        else:
            result.responsive = "RED"
    return result


def _find_button(page: Page, text: str, timeout: float = 20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for frame in page.frames:
            try:
                loc = frame.get_by_role("button", name=text)
                if loc.count() > 0:
                    return loc.first
            except Exception:
                pass
        time.sleep(0.25)
    raise RuntimeError(f"BUTTON_NOT_READY:{text}")


def _audit_mlb_live_odds(page: Page, base_url: str, *, steps23_only: bool = False) -> RouteResult:
    result = RouteResult("MLB", "MLB", "MLB Live Odds")
    try:
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.goto(_route_url(base_url, "MLB", "Slate"), wait_until="domcontentloaded", timeout=120_000)
        _wait_for_meaningful_route(page, sport_code="MLB", sport_label="MLB", market="Slate")
        button = _find_button(page, "MLB Live Odds")
        button.click()
        started = time.monotonic()
        deadline = started + 45
        last = ""
        while time.monotonic() < deadline:
            last = _all_frame_text(page)
            fatal = _fatal_marker(last)
            if fatal:
                raise RuntimeError(f"FATAL_RENDER:{fatal}")
            if "MLB Live Odds" in last and len(" ".join(last.split())) >= 220:
                break
            time.sleep(0.35)
        else:
            raise RuntimeError("MLB_LIVE_ODDS_FIRST_RENDER_NOT_READY")
        result.first_render_seconds = round(time.monotonic() - started, 3)
        result.smoke = "GREEN"
        result.flow = "GREEN"

        if steps23_only:
            result.responsive = "NOT_REQUIRED"
            return result

        for width, height in WIDTHS:
            page.set_viewport_size({"width": width, "height": height})
            time.sleep(0.25)
            current = _all_frame_text(page)
            fatal = _fatal_marker(current)
            if fatal:
                raise RuntimeError(f"RESPONSIVE_FATAL:{width}:{fatal}")
            overflow, detail = _root_overflow(page)
            if overflow:
                raise RuntimeError(f"ROOT_OVERFLOW:{width}:{detail}")
        result.responsive = "GREEN"
    except Exception as exc:
        result.detail = f"{type(exc).__name__}:{exc}"[:1200]
        if result.smoke != "GREEN":
            result.smoke = "RED"
        elif result.flow != "GREEN":
            result.flow = "RED"
        else:
            result.responsive = "RED"
    return result


def _inventory_contract() -> None:
    all_routes = list(ROUTES) + list(SPECIAL_ROUTES)
    assert len(all_routes) == EXPECTED_ROUTE_COUNT, len(all_routes)
    assert len(set(all_routes)) == EXPECTED_ROUTE_COUNT
    assert ("NFL", "NFL", "Passing Yards") in ROUTES
    assert ("MLB", "MLB", "MLB Live Odds") in SPECIAL_ROUTES
    counts: dict[str, int] = {}
    for code, _label, _market in all_routes:
        counts[code] = counts.get(code, 0) + 1
    assert counts == {"NFL": 11, "CFB": 3, "MLB": 13, "WNBA": 9}, counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=PUBLIC_BASE_URL)
    parser.add_argument("--json-out", default="")
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--only-sport", default="")
    parser.add_argument("--only-market", default="")
    parser.add_argument(
        "--steps23-only",
        action="store_true",
        help="Certify first meaningful render + route handoff only; do not require idle/responsive completion.",
    )
    args = parser.parse_args()

    _inventory_contract()
    print("SITEWIDE_PAGE_LOAD_STEP1_INVENTORY_GREEN routes=36")
    if args.inventory_only:
        return 0

    selected_routes = list(ROUTES)
    if args.only_sport:
        selected_routes = [row for row in selected_routes if row[0] == args.only_sport]
    if args.only_market:
        selected_routes = [row for row in selected_routes if row[2] == args.only_market]
    include_live_odds = (
        not args.only_sport and not args.only_market
    ) or (
        args.only_sport == "MLB" and args.only_market == "MLB Live Odds"
    )
    if not selected_routes and not include_live_odds:
        raise SystemExit("SITEWIDE_PAGE_LOAD_FILTER_MATCHED_NO_ROUTES")

    results: list[RouteResult] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()

        for row in selected_routes:
            result = _audit_normal_route(page, args.base_url, row, steps23_only=args.steps23_only)
            results.append(result)
            icon = "GREEN" if (
                result.smoke == "GREEN"
                and result.flow == "GREEN"
                and (args.steps23_only or result.responsive == "GREEN")
            ) else "RED"
            print(
                f"SITEWIDE_ROUTE_{icon} "
                f"sport={result.sport_code!r} market={result.market!r} "
                f"smoke={result.smoke} flow={result.flow} responsive={result.responsive} "
                f"seconds={result.first_render_seconds} detail={result.detail!r}"
            )

        if include_live_odds:
            result = _audit_mlb_live_odds(page, args.base_url, steps23_only=args.steps23_only)
            results.append(result)
            icon = "GREEN" if (
                result.smoke == "GREEN"
                and result.flow == "GREEN"
                and (args.steps23_only or result.responsive == "GREEN")
            ) else "RED"
            print(
                f"SITEWIDE_ROUTE_{icon} sport='MLB' market='MLB Live Odds' "
                f"smoke={result.smoke} flow={result.flow} responsive={result.responsive} "
                f"seconds={result.first_render_seconds} detail={result.detail!r}"
            )

        context.close()
        browser.close()

    payload = {
        "base_url": args.base_url,
        "route_count": len(results),
        "results": [asdict(r) for r in results],
    }
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, sort_keys=True))

    smoke_bad = [r for r in results if r.smoke != "GREEN"]
    flow_bad = [r for r in results if r.flow != "GREEN"]
    responsive_bad = [] if args.steps23_only else [r for r in results if r.responsive != "GREEN"]

    print(f"SITEWIDE_PAGE_LOAD_SUMMARY routes={len(results)} smoke_bad={len(smoke_bad)} flow_bad={len(flow_bad)} responsive_bad={len(responsive_bad)}")

    if smoke_bad or flow_bad or responsive_bad:
        for r in results:
            if r.smoke != "GREEN" or r.flow != "GREEN" or (not args.steps23_only and r.responsive != "GREEN"):
                print(
                    "SITEWIDE_PAGE_LOAD_FAILURE "
                    f"sport={r.sport_code!r} market={r.market!r} "
                    f"smoke={r.smoke} flow={r.flow} responsive={r.responsive} "
                    f"detail={r.detail!r}"
                )
        return 1

    if len(results) == EXPECTED_ROUTE_COUNT:
        print("SITEWIDE_PAGE_LOAD_STEP2_PUBLIC_SMOKE_GREEN")
        print("SITEWIDE_PAGE_LOAD_STEP2_FROZEN")
        print("SITEWIDE_PAGE_LOAD_STEP3_USER_FLOW_GREEN")
        print("SITEWIDE_PAGE_LOAD_STEP3_FROZEN")
        if not args.steps23_only:
            print("SITEWIDE_PAGE_LOAD_STEP4_NO_BROKEN_ROUTES_GREEN")
            print("SITEWIDE_PAGE_LOAD_STEP5_REPAIR_CERTIFIED_GREEN")
            print("SITEWIDE_PAGE_LOAD_STEP6_RESPONSIVE_RUNTIME_GREEN")
            print("SITEWIDE_PAGE_LOAD_STEP6_GREEN")
            print("SITEWIDE_PAGE_LOAD_STEP6_FROZEN")
    else:
        token = (
            "SITEWIDE_PAGE_LOAD_STEPS23_BRANCH_TARGET_GREEN"
            if args.steps23_only
            else "SITEWIDE_PAGE_LOAD_BRANCH_TARGET_GREEN"
        )
        print(f"{token} routes={len(results)} base_url={args.base_url!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
