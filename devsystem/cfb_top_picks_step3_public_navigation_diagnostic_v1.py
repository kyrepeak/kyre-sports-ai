"""CFB Step 3 public click-vs-direct navigation diagnostic.

Diagnostic-only. Compares the current card-click detail handoff with opening
the exact same resolved detail URL directly. It does not mutate product,
router, model, ranking, probability, selection, sportsbook, API2, or registry.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.sync_api import sync_playwright
from devsystem import cfb_top_picks_nav_step3_public_cert_v1 as public_nav

PUBLIC_URL = "https://pickvault.streamlit.app"
CFB_V5_ROOT = '[data-testid="cfb-top-picks-step5-root"][data-cfb-top-picks-visual="v5"]'
CFB_V9_MARKER = '[data-testid="cfb-top-picks-research-v2-step9-marker"]'
REASONING = '[data-testid^="cfb-top-picks-market-reasoning-"][data-reasoning-status]'
DETAIL_LINK = 'a[href*="top_pick_detail="]'
EXPANDED_DETAIL = 'details.tp4-details[data-expanded="true"]'
DETAIL_PANEL = '[data-testid^="cfb-top-picks-detail-panel-"]'
LOADING_TEXT = "Loading verified historical context for this selected matchup only."
ROUTE_KEYS = ("ks_sport","ks_cfb_market","top_pick_detail","ks_jump_sport","ks_jump_market")
WNBA_MARKERS = {
    "repair_step3": '[data-wnba-pra-repair-v1-step3="data-completeness"]',
    "nav_step7": '[data-wnba-nav-v2-step7="final-transport"]',
    "nav_step6": '[data-wnba-nav-v2-step6="responsive-integration"]',
    "nav_step5": '[data-wnba-nav-v2-step5="performance"]',
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _query(url: str) -> dict[str, str]:
    raw = parse_qs(urlparse(url or "").query)
    return {k: (v[-1] if v else "") for k, v in raw.items()}


def _route_values(outer_url: str, frame_url: str) -> dict[str, str]:
    outer, frame = _query(outer_url), _query(frame_url)
    return {k: _clean(frame.get(k) or outer.get(k)) for k in ROUTE_KEYS}


def _count(scope: Any, selector: str) -> int:
    try:
        return int(scope.locator(selector).count())
    except Exception:
        return 0


def _all_count(page: Any, selector: str) -> int:
    return sum(_count(frame, selector) for frame in page.frames)


def _body(frame: Any) -> str:
    try:
        return _clean(frame.locator("body").inner_text(timeout=2500))
    except Exception:
        return ""


def _score(frame: Any) -> int:
    score = 10000 * _count(frame, CFB_V5_ROOT)
    score += 9000 * _count(frame, REASONING)
    score += 8000 * _count(frame, CFB_V9_MARKER)
    for selector in WNBA_MARKERS.values():
        score += 7000 * _count(frame, selector)
    body = _body(frame)
    score += 500 if "KYRE SPORTS AI" in body else 0
    score += 300 if "Top Picks" in body else 0
    score += 250 if "WNBA" in body else 0
    score += 150 if "PRA" in body else 0
    return score


def _best_frame(page: Any) -> Any:
    frames = list(page.frames)
    return max(frames, key=_score) if frames else page.main_frame


def _find_detail(page: Any):
    for frame in page.frames:
        try:
            loc = frame.locator(DETAIL_LINK)
            if loc.count() > 0 and loc.first.is_visible():
                return frame, loc.first
        except Exception:
            pass
    raise AssertionError("DIAGNOSTIC_DETAIL_LINK_MISSING")


def _capture(page: Any, frame: Any, *, path: str, before: dict[str, str], href: str, resolved: str) -> dict[str, Any]:
    outer_url = _clean(page.url)
    frame_url = _clean(getattr(frame, "url", ""))
    route = _route_values(outer_url, frame_url)
    cfb_v5 = _all_count(page, CFB_V5_ROOT)
    cfb_v9 = _all_count(page, CFB_V9_MARKER)
    reasoning_count = _all_count(page, REASONING)
    wnba = {name: _all_count(page, selector) for name, selector in WNBA_MARKERS.items()}

    status = ""
    heading = ""
    if reasoning_count:
        for current in page.frames:
            try:
                loc = current.locator(REASONING)
                if loc.count():
                    status = _clean(loc.first.get_attribute("data-reasoning-status")).upper()
                    h4 = loc.first.locator("h4")
                    if h4.count():
                        heading = _clean(h4.first.text_content(timeout=3000))
                    break
            except Exception:
                pass

    wnba_total = sum(wnba.values())
    owner = "CFB_TOP_PICKS" if cfb_v5 else ("WNBA_PRA" if wnba_total else "UNKNOWN")
    expected_detail = _clean(_query(resolved).get("top_pick_detail"))

    current_detail_ids = []
    panel_text = ""
    for current in page.frames:
        try:
            links = current.locator(DETAIL_LINK)
            for index in range(links.count()):
                value = _clean(links.nth(index).get_attribute("href"))
                event_id = _clean(_query(value).get("top_pick_detail"))
                if event_id:
                    current_detail_ids.append(event_id)
        except Exception:
            pass
        try:
            panels = current.locator(DETAIL_PANEL)
            if panels.count() > 0 and not panel_text:
                panel_text = _clean(panels.first.inner_text(timeout=2500))
        except Exception:
            pass

    expanded_detail_count = _all_count(page, EXPANDED_DETAIL)
    detail_panel_count = _all_count(page, DETAIL_PANEL)
    selected_event_still_collapsed = expected_detail in current_detail_ids
    loading_placeholder_present = LOADING_TEXT in panel_text
    if route["ks_sport"] != "College Football":
        divergent = "ks_sport"
    elif route["ks_cfb_market"] != "Top Picks":
        divergent = "ks_cfb_market"
    elif route["top_pick_detail"] != expected_detail:
        divergent = "top_pick_detail"
    elif wnba_total:
        divergent = "wnba_pra_owner_with_cfb_query"
    elif selected_event_still_collapsed and expanded_detail_count == 0:
        divergent = "selected_event_not_expanded"
    elif detail_panel_count > 0 and loading_placeholder_present:
        divergent = "detail_stuck_loading"
    elif cfb_v5 == 0:
        divergent = "cfb_v5_root_missing"
    elif cfb_v9 == 0:
        divergent = "cfb_v9_marker_missing"
    elif reasoning_count == 0:
        divergent = "market_reasoning_selector_missing"
    else:
        divergent = "none"

    return {
        "path": path,
        "outer_url_before": before["outer_url"],
        "frame_url_before": before["frame_url"],
        "href": href,
        "resolved_detail_url": resolved,
        "outer_url_after": outer_url,
        "frame_url_after": frame_url,
        **route,
        "cfb_v5_root_count": cfb_v5,
        "cfb_v9_marker_count": cfb_v9,
        "reasoning_selector_count": reasoning_count,
        "reasoning_status": status,
        "heading": heading,
        "wnba_pra_marker_counts": wnba,
        "visible_root_owner": owner,
        "card_detail_event_ids_after": sorted(set(current_detail_ids)),
        "selected_event_still_collapsed": selected_event_still_collapsed,
        "expanded_detail_count": expanded_detail_count,
        "detail_panel_count": detail_panel_count,
        "loading_placeholder_present": loading_placeholder_present,
        "detail_panel_text_start": panel_text[:500],
        "first_divergent_state": divergent,
    }


def _green(e: dict[str, Any]) -> bool:
    return (
        e["cfb_v5_root_count"] >= 1
        and e["cfb_v9_marker_count"] == 1
        and e["reasoning_selector_count"] == 1
        and e["reasoning_status"] in {"READY", "PARTIAL"}
        and e["heading"] == "Market-Aware Football Reasoning"
    )


def _wait_capture(page: Any, *, path: str, before: dict[str, str], href: str, resolved: str) -> dict[str, Any]:
    deadline = time.monotonic() + 120.0
    latest = None
    while time.monotonic() < deadline:
        latest = _capture(page, _best_frame(page), path=path, before=before, href=href, resolved=resolved)
        if _green(latest):
            return latest
        page.wait_for_timeout(1000)
    assert latest is not None
    return latest


def _classify(click: dict[str, Any], direct: dict[str, Any]) -> tuple[str, str]:
    click_green, direct_green = _green(click), _green(direct)
    cfb_query_present = (
        click["ks_sport"] == "College Football"
        and click["ks_cfb_market"] == "Top Picks"
        and bool(click["top_pick_detail"])
    )
    if not click_green and cfb_query_present and sum(click["wnba_pra_marker_counts"].values()) > 0:
        return "CASE_4", "EARLY_WNBA_TRAMPOLINE_ROUTER_OWNERSHIP"
    if not click_green and direct_green:
        return "CASE_1", "PUBLIC_CLICK_SESSION_FRAME_HANDOFF_DEFECT"
    if not click_green and not direct_green:
        return "CASE_2", "REAL_ROUTER_OWNERSHIP_DEFECT"
    if click_green and direct_green:
        return "CASE_3", "PROOF_VERIFIER_DEFECT"
    return "UNSPECIFIED_ASYMMETRY", "DIRECT_PATH_ONLY_FAILURE"


def run(*, base_url: str, artifact_dir: str | Path, main_sha: str, run_id: str) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport={"width": 390, "height": 844})
        try:
            click_page = context.new_page()
            public_nav._attempt_normal_flow(click_page, base_url, 390, 844)
            click_frame, link = _find_detail(click_page)
            before = {"outer_url": _clean(click_page.url), "frame_url": _clean(click_frame.url)}
            href = _clean(link.get_attribute("href"))
            if "top_pick_detail=" not in href:
                raise AssertionError("DIAGNOSTIC_DETAIL_HREF_INVALID:" + href)
            join_base = before["frame_url"] if before["frame_url"].startswith("http") else before["outer_url"]
            resolved = urljoin(join_base or base_url, href)
            click_page.screenshot(path=str(artifacts / "path_a_before_click.png"), full_page=True)

            link.click(timeout=15000)
            click_page.wait_for_timeout(1500)
            click_evidence = _wait_capture(click_page, path="click", before=before, href=href, resolved=resolved)
            click_page.screenshot(path=str(artifacts / "path_a_after_click.png"), full_page=True)

            direct_page = context.new_page()
            direct_before = {"outer_url": _clean(direct_page.url), "frame_url": _clean(direct_page.main_frame.url)}
            direct_page.goto(resolved, wait_until="domcontentloaded", timeout=120000)
            direct_evidence = _wait_capture(direct_page, path="direct", before=direct_before, href=href, resolved=resolved)
            direct_page.screenshot(path=str(artifacts / "path_b_direct_detail.png"), full_page=True)

            case, classification = _classify(click_evidence, direct_evidence)
            click_evidence["classification"] = classification
            direct_evidence["classification"] = classification
            payload = {
                "status": "DIAGNOSTIC_COMPLETE",
                "main_sha": main_sha,
                "run_id": run_id,
                "source_failed_public_run_id": "37148788864",
                "decision_case": case,
                "classification": classification,
                "click_green": _green(click_evidence),
                "direct_green": _green(direct_evidence),
                "first_divergent_state": click_evidence["first_divergent_state"],
                "product_mutation": False,
                "click": click_evidence,
                "direct": direct_evidence,
            }
            (artifacts / "public_navigation_diagnostic.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print("CFB_TOP_PICKS_STEP3_PUBLIC_NAV_DIAGNOSTIC_COMPLETE")
            print("CFB_TOP_PICKS_STEP3_PUBLIC_NAV_DIAGNOSTIC_CLASSIFICATION=" + classification)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return payload
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=PUBLIC_URL)
    parser.add_argument("--artifact-dir", default="artifacts/cfb-step3-public-navigation-diagnostic")
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run(base_url=args.base_url, artifact_dir=args.artifact_dir, main_sha=args.main_sha, run_id=args.run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
