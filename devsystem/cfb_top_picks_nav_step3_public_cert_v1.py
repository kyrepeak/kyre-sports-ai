"""CFB Top Picks Navigation Step 3 — public production freeze verifier."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from playwright.sync_api import sync_playwright

from devsystem import browser_qa_v1 as base
from devsystem import user_visible_contract_v1 as user_contract

PUBLIC_URL = "https://pickvault.streamlit.app"
CFB_SPORT = "College Football"
CFB_MARKET_LABEL = "🎯 CFB Market"
TOP_PICKS = "Top Picks"
EXPECTED_CFB_MARKETS = ("Moneyline", "Over/Under", "Game Total", "Top Picks")
V5_ROOT = '[data-testid="cfb-top-picks-step5-root"][data-cfb-top-picks-visual="v5"]'
V5_MARKER = "CFB_TOP_PICKS_STEP5_FINAL_VISUAL_ACTIVE"
WIDTHS = user_contract.RESPONSIVE_VIEWPORTS
TOP_PICKS_USER_CONTRACT = user_contract.UserVisibleContract(
    name="cfb-top-picks-v5",
    required_selectors=(V5_ROOT,),
    required_text=(V5_MARKER, "Top Picks", "10 Best Daily College Football Picks"),
    required_markets=EXPECTED_CFB_MARKETS,
    required_viewports=WIDTHS,
    query_policy=user_contract.QUERY_POLICY_TELEMETRY,
    required_query=(("ks_sport", CFB_SPORT), ("ks_cfb_market", TOP_PICKS)),
)


def _wait_http(base_url: str, timeout_seconds: float = 180.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last = None
    while time.monotonic() < deadline:
        try:
            r = requests.get(
                base_url.rstrip("/") + "/",
                timeout=7,
                headers={"User-Agent": "KyreSportsAI-TopPicksNavStep3/1.0"},
            )
            last = r.status_code
            if r.status_code < 500:
                return
        except Exception:
            pass
        time.sleep(2)
    raise AssertionError(f"CFB_TOP_PICKS_NAV_STEP3_PUBLIC_HTTP_NOT_READY:{last}")


def _body(page) -> str:
    values = []
    for frame in page.frames:
        try:
            values.append(frame.locator("body").inner_text(timeout=2500))
        except Exception:
            pass
    return "\n".join(values)


def _query(page) -> dict[str, list[str]]:
    return parse_qs(urlparse(page.url).query)


def _visible_options(page, frame, timeout_seconds: float = 15.0):
    """Resolve Streamlit's option portal in either iframe or outer page."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        for scope in (frame, page):
            try:
                locator = scope.get_by_role("option")
                if locator.count() > 0 and locator.first.is_visible():
                    return locator
            except Exception:
                pass
        page.wait_for_timeout(200)
    raise AssertionError(
        "CFB_TOP_PICKS_NAV_STEP3_PUBLIC_OPTIONS_NOT_VISIBLE:" + _body(page)[:4000]
    )


def _market_options(page, frame) -> list[str]:
    # Responsive resize can trigger a Streamlit rerun where the combobox is
    # already visible but its portal has not finished hydrating. Retry the
    # open/read cycle until the complete frozen market set is actually present.
    deadline = time.monotonic() + 30.0
    last_values: list[str] = []
    last_error = ""
    while time.monotonic() < deadline:
        try:
            combo = frame.get_by_role("combobox", name=CFB_MARKET_LABEL, exact=True)
            combo.wait_for(state="visible", timeout=5000)
            combo.click(timeout=5000)
            options_locator = _visible_options(page, frame, timeout_seconds=3.0)
            values = [v.strip() for v in options_locator.all_inner_texts() if v.strip()]
            last_values = values
            if all(option in values for option in EXPECTED_CFB_MARKETS):
                page.keyboard.press("Escape")
                return values
        except Exception as exc:
            last_error = repr(exc)
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        page.wait_for_timeout(250)
    raise AssertionError(
        "CFB_TOP_PICKS_NAV_STEP3_PUBLIC_MARKET_OPTIONS_NOT_READY:"
        f"saw={last_values!r};last={last_error}"
    )


def _click_option(page, frame, value: str) -> None:
    combo = frame.get_by_role("combobox", name=CFB_MARKET_LABEL, exact=True)
    combo.wait_for(state="visible", timeout=45000)
    combo.click()
    # Streamlit's portal can briefly expose only the selected option while a
    # rerun hydrates the rest of the market list. Treat that as readiness, not
    # as a terminal missing-option verdict.
    deadline = time.monotonic() + 20.0
    labels: list[str] = []
    last_error = ""
    while time.monotonic() < deadline:
        try:
            options = _visible_options(page, frame, timeout_seconds=2.0)
            labels = [v.strip() for v in options.all_inner_texts()]
            if value in labels:
                for scope in (frame, page):
                    try:
                        target = scope.get_by_role("option", name=value, exact=True)
                        if target.count() > 0 and target.first.is_visible():
                            target.first.click(timeout=10000)
                            return
                    except Exception as exc:
                        last_error = repr(exc)
        except Exception as exc:
            last_error = repr(exc)
        page.wait_for_timeout(250)
    raise AssertionError(
        f"CFB_TOP_PICKS_NAV_STEP3_PUBLIC_OPTION_MISSING:{value!r};"
        f"saw={labels!r};last={last_error}"
    )


def _find_v5(page, timeout_seconds: float = 180.0):
    deadline = time.monotonic() + timeout_seconds
    last_body = ""
    while time.monotonic() < deadline:
        last_body = _body(page)
        forbidden = base._body_has_forbidden_error(last_body)
        if forbidden:
            raise AssertionError(
                f"CFB_TOP_PICKS_NAV_STEP3_PUBLIC_RUNTIME_ERROR:{forbidden}:{last_body[:4000]}"
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
        "CFB_TOP_PICKS_NAV_STEP3_PUBLIC_V5_NOT_READY:" + last_body[:5000]
    )


def _assert_query(page, timeout_seconds: float = 15.0) -> dict[str, list[str]]:
    """Allow Streamlit's client URL to catch up with the already-rendered V5 route."""
    deadline = time.monotonic() + timeout_seconds
    last = {}
    while time.monotonic() < deadline:
        parsed = _query(page)
        last = parsed
        sport = (parsed.get("ks_sport") or [""])[-1]
        market = (parsed.get("ks_cfb_market") or [""])[-1]
        if sport == CFB_SPORT and market == TOP_PICKS:
            return parsed
        page.wait_for_timeout(250)

    sport = (last.get("ks_sport") or [""])[-1]
    market = (last.get("ks_cfb_market") or [""])[-1]
    raise AssertionError(
        "CFB_TOP_PICKS_NAV_STEP3_PUBLIC_QUERY_MISMATCH:"
        f"sport={sport!r};market={market!r};url={page.url!r}"
    )


def _attempt_normal_flow(page, base_url: str, width: int, height: int) -> dict:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(
        base_url.rstrip("/") + "/",
        wait_until="domcontentloaded",
        timeout=120000,
    )
    frame, initial_scan = base._find_app_frame(page, timeout_seconds=90.0)
    base._choose(page, frame, 0, CFB_SPORT)

    frame, cfb_scan = base._find_app_frame(page, timeout_seconds=90.0)
    before = _market_options(page, frame)
    missing = [x for x in EXPECTED_CFB_MARKETS if x not in before]
    if missing:
        raise AssertionError(
            f"CFB_TOP_PICKS_NAV_STEP3_PUBLIC_MENU_STALE:{missing!r};saw={before!r}"
        )
    if before.count(TOP_PICKS) != 1:
        raise AssertionError(
            "CFB_TOP_PICKS_NAV_STEP3_PUBLIC_TOP_PICKS_COUNT:"
            + str(before.count(TOP_PICKS))
        )

    _click_option(page, frame, TOP_PICKS)

    v5_frame, root = _find_v5(page)

    # Step 4 contract-first acceptance: rendered user behavior blocks;
    # URL/query state is retained as telemetry unless a feature explicitly
    # declares it REQUIRED.
    query = _query(page)
    after = _market_options(page, v5_frame)
    contract_evidence = user_contract.certify_playwright_surface(
        page=page,
        frame=v5_frame,
        contract=TOP_PICKS_USER_CONTRACT,
        observed_markets=after,
        query=query,
    )
    dims = contract_evidence["dimensions"]

    return {
        "width": width,
        "height": height,
        "before_options": before,
        "after_options": after,
        "query": query,
        "v5_root_count": root.count(),
        "dims": dims,
        "status": contract_evidence["status"],
        "user_visible_contract": contract_evidence,
        "initial_scan": initial_scan,
        "cfb_scan": cfb_scan,
    }


def _certify_current_v5_width(
    page,
    width: int,
    height: int,
    *,
    screenshot_path: str | Path | None = None,
) -> dict:
    """Resize the already-rendered V5 surface without re-running navigation."""
    page.set_viewport_size({"width": width, "height": height})
    v5_frame, root = _find_v5(page)
    query = _query(page)
    after = _market_options(page, v5_frame)
    contract_evidence = user_contract.certify_playwright_surface(
        page=page,
        frame=v5_frame,
        contract=TOP_PICKS_USER_CONTRACT,
        observed_markets=after,
        query=query,
    )
    if screenshot_path is not None:
        page.screenshot(path=str(screenshot_path), full_page=True)
    return {
        "width": width,
        "height": height,
        "after_options": after,
        "query": query,
        "v5_root_count": root.count(),
        "dims": contract_evidence["dimensions"],
        "status": contract_evidence["status"],
        "user_visible_contract": contract_evidence,
        "responsive_only": True,
    }


def run(*, base_url: str, artifact_dir: str | Path) -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    _wait_http(base_url)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = None
        try:
            results = []
            deadline = time.monotonic() + 600.0
            last_error = ""

            # Prove the real navigation exactly once. A fresh page is used only
            # when retrying deployment readiness before that first success.
            while time.monotonic() < deadline:
                if page is not None:
                    page.close()
                page = browser.new_page(
                    viewport={"width": WIDTHS[0][0], "height": WIDTHS[0][1]}
                )
                try:
                    first = _attempt_normal_flow(page, base_url, *WIDTHS[0])
                    page.screenshot(
                        path=str(
                            artifacts / "cfb_top_picks_nav_step3_public_390_green.png"
                        ),
                        full_page=True,
                    )
                    results.append(first)
                    break
                except Exception as exc:
                    last_error = repr(exc)
                    page.close()
                    page = None
                    time.sleep(6)
            else:
                raise AssertionError(
                    "CFB_TOP_PICKS_NAV_STEP3_PUBLIC_DEPLOY_NOT_ACTIVE:" + last_error
                )

            print("CFB_TOP_PICKS_NAV_STEP3_PUBLIC_DROPDOWN_GREEN")
            print("CFB_TOP_PICKS_NAV_STEP3_PUBLIC_V5_ROUTE_GREEN")
            print("CFB_TOP_PICKS_NAV_STEP3_PUBLIC_390_GREEN")

            # Responsive certification resizes the already-rendered V5 surface.
            # Do not restart the route state machine for each viewport.
            for width, height in WIDTHS[1:]:
                result = _certify_current_v5_width(
                    page,
                    width,
                    height,
                    screenshot_path=artifacts
                    / f"cfb_top_picks_nav_step3_public_{width}_green.png",
                )
                results.append(result)
                print(f"CFB_TOP_PICKS_NAV_STEP3_PUBLIC_{width}_GREEN")

            responsive_contract = user_contract.certify_responsive_suite(
                TOP_PICKS_USER_CONTRACT,
                [item["user_visible_contract"] for item in results],
            )
            payload = {
                "status": "GREEN",
                "host": base_url,
                "flow": "normal app -> College Football -> Top Picks",
                "responsive_method": "single navigation then resize rendered V5",
                "expected_markets": list(EXPECTED_CFB_MARKETS),
                "user_visible_contract": responsive_contract,
                "results": results,
            }
            (artifacts / "cfb_top_picks_nav_step3_public_evidence.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print("CFB_TOP_PICKS_NAV_STEPS1_3_PUBLIC_GREEN")
            print("CFB_TOP_PICKS_NAV_STEPS1_3_FROZEN_GREEN")
            print(json.dumps(payload, indent=2, sort_keys=True))
            return payload
        finally:
            if page is not None:
                page.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=PUBLIC_URL)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/cfb-top-picks-nav-step3-public",
    )
    args = parser.parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
