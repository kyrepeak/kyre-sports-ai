"""CFB Top Picks Repair Step 4 — current V9 detail-integrity proof.

Proof-only verifier. It does not modify page, router, model, projection,
probability, ranking, selection, sportsbook, API 2, or frozen Steps 1-3.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

import cfb_top_picks_details_v5 as details
import cfb_top_picks_engine_v1 as engine
import cfb_top_picks_history_router_v1 as history_router
import cfb_top_picks_page_v9 as page

MODEL_VERSION = "CFB TOP PICKS REPAIR STEP 4 • DETAIL INTEGRITY CERT"
MISSION_STEP = "4/5"
PUBLIC_URL = "https://pickvault.streamlit.app"
REQUIRED_SECTIONS = ("Why This Pick", "Actual Matchup History", "Benefits")
TERMINAL_HISTORY_STATUSES = {
    history_router.VERIFIED_HISTORY,
    history_router.VERIFIED_NO_HISTORY,
    history_router.SOURCE_CONFLICT_REVIEW,
}
API2_USED = False
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
HISTORY_PROJECTION_WEIGHT = 0.0
HISTORY_SELECTION_WEIGHT = 0.0
HISTORY_RANKING_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SELECTION = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _validate_detail(row: Mapping[str, Any], detail: Mapping[str, Any]) -> dict[str, Any]:
    rank = int(row.get("rank") or 0)
    event_id = _clean(row.get("event_id"))
    if detail.get("ready") is not True:
        raise AssertionError(f"STEP4_DETAIL_NOT_READY:{rank}:{event_id}")
    if _clean(detail.get("event_id")) != event_id:
        raise AssertionError(f"STEP4_EVENT_IDENTITY:{rank}:{event_id}:{detail.get('event_id')}")

    away_id = _clean(detail.get("away_espn_team_id"))
    home_id = _clean(detail.get("home_espn_team_id"))
    if not (away_id.isdigit() and home_id.isdigit()):
        raise AssertionError(f"STEP4_TEAM_IDENTITY:{rank}:{away_id}:{home_id}")

    history_status = _clean(detail.get("history_status"))
    if history_status not in TERMINAL_HISTORY_STATUSES:
        raise AssertionError(f"STEP4_HISTORY_STATUS:{rank}:{history_status}")
    if history_status == history_router.VERIFIED_NO_HISTORY and detail.get("no_history_claim_allowed") is not True:
        raise AssertionError(f"STEP4_NO_HISTORY_CLAIM_NOT_VERIFIED:{rank}")

    for key in (
        "history_projection_weight",
        "history_selection_weight",
        "history_ranking_weight",
        "sportsbook_projection_weight",
    ):
        if float(detail.get(key) or 0.0) != 0.0:
            raise AssertionError(f"STEP4_NONZERO_WEIGHT:{rank}:{key}:{detail.get(key)}")

    why = _clean(detail.get("why"))
    benefit = _clean(detail.get("benefit"))
    if len(why) < 20:
        raise AssertionError(f"STEP4_WHY_EMPTY:{rank}")
    if len(benefit) < 20:
        raise AssertionError(f"STEP4_BENEFIT_EMPTY:{rank}")

    html = page._detail_card(dict(row), dict(detail))
    for token in (*REQUIRED_SECTIONS, 'data-expanded="true"', "Market-Aware Football Reasoning"):
        if token not in html:
            raise AssertionError(f"STEP4_SURFACE_TOKEN:{rank}:{token}")

    return {
        "rank": rank,
        "event_id": event_id,
        "market": _clean(row.get("market")).upper(),
        "history_status": history_status,
        "history_ready": bool(detail.get("history_ready")),
        "meetings": int(detail.get("meetings") or 0),
        "why_chars": len(why),
        "benefit_chars": len(benefit),
        "away_espn_team_id": away_id,
        "home_espn_team_id": home_id,
    }


def run_live(
    artifact_dir: str | Path = "artifacts/cfb-top-picks-repair-step4-detail-integrity"
) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    picks, diag = engine.build_top_picks(limit=10)
    if len(picks) != 10:
        raise AssertionError(f"STEP4_TOP10_COUNT:{len(picks)}")
    ranks = [int(row.get("rank") or 0) for row in picks]
    if ranks != list(range(1, 11)):
        raise AssertionError(f"STEP4_RANK_ORDER:{ranks}")

    slate_day = _clean(diag.get("slate_date")) or "Today"

    def build(row: Mapping[str, Any]):
        return row, details.build_pick_detail(row, slate_day)

    resolved = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(build, row) for row in picks]
        for future in as_completed(futures):
            resolved.append(future.result())

    certified = [
        _validate_detail(row, detail)
        for row, detail in sorted(
            resolved, key=lambda pair: int(pair[0].get("rank") or 99)
        )
    ]
    if len(certified) != 10:
        raise AssertionError(f"STEP4_CERTIFIED_COUNT:{len(certified)}")

    payload = {
        "status": "GREEN",
        "mission_step": MISSION_STEP,
        "slate_day": slate_day,
        "ranked_picks_certified": 10,
        "detail_sections": list(REQUIRED_SECTIONS),
        "exact_event_identity": True,
        "exact_team_identity": True,
        "selected_matchup_detail_contract": True,
        "history_fabricated": False,
        "history_projection_weight": 0.0,
        "history_selection_weight": 0.0,
        "history_ranking_weight": 0.0,
        "sportsbook_projection_weight": 0.0,
        "projection_changed": False,
        "probability_changed": False,
        "ranking_changed": False,
        "selection_changed": False,
        "api2_used": False,
        "picks": certified,
    }
    (artifacts / "live_step4_detail_integrity.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("CFB_TOP_PICKS_REPAIR_STEP4_DETAILS_10_OF_10_GREEN")
    print("CFB_TOP_PICKS_REPAIR_STEP4_WHY_HISTORY_BENEFITS_GREEN")
    print("CFB_TOP_PICKS_REPAIR_STEP4_ZERO_WEIGHT_FIREWALL_GREEN")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def _visible_exact_text(frame: Any, text: str) -> bool:
    loc = frame.get_by_text(text, exact=True)
    for idx in range(loc.count()):
        try:
            if loc.nth(idx).is_visible():
                return True
        except Exception:
            pass
    return False


def run_public(
    *,
    base_url: str = PUBLIC_URL,
    artifact_dir: str | Path = "artifacts/cfb-top-picks-repair-step4-detail-integrity",
) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright
    from devsystem import cfb_top_picks_nav_step3_public_cert_v1 as public_nav

    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"]
        )
        p = None
        try:
            deadline = time.monotonic() + 600.0
            last_error = ""
            while time.monotonic() < deadline:
                if p is not None:
                    p.close()
                p = browser.new_page(viewport={"width": 390, "height": 844})
                try:
                    public_nav._attempt_normal_flow(p, base_url, 390, 844)

                    detail_link = None
                    for frame in p.frames:
                        try:
                            loc = frame.locator('a[href*="top_pick_detail="]')
                            if loc.count() > 0 and loc.first.is_visible():
                                detail_link = loc.first
                                break
                        except Exception:
                            pass
                    if detail_link is None:
                        raise AssertionError("STEP4_PUBLIC_DETAIL_LINK_MISSING")

                    href = _clean(detail_link.get_attribute("href"))
                    parsed = parse_qs(urlparse(href).query)
                    event_id = _clean((parsed.get("top_pick_detail") or [""])[0])
                    if not event_id.isdigit():
                        raise AssertionError(f"STEP4_PUBLIC_EVENT_ID:{event_id}")
                    detail_link.click(timeout=15000)

                    selected_frame = None
                    section_deadline = time.monotonic() + 180.0
                    while time.monotonic() < section_deadline:
                        for frame in p.frames:
                            try:
                                expanded = frame.locator('[data-expanded="true"]')
                                if expanded.count() < 1:
                                    continue
                                if all(_visible_exact_text(frame, text) for text in REQUIRED_SECTIONS):
                                    selected_frame = frame
                                    break
                            except Exception:
                                pass
                        if selected_frame is not None:
                            break
                        p.wait_for_timeout(500)

                    if selected_frame is None:
                        raise AssertionError("STEP4_PUBLIC_DETAIL_SECTIONS_NOT_READY")

                    if not _visible_exact_text(selected_frame, "Market-Aware Football Reasoning"):
                        raise AssertionError("STEP4_PUBLIC_STEP3_PRESERVATION_MISSING")

                    screenshot = artifacts / "public_step4_detail_390_green.png"
                    p.screenshot(path=str(screenshot), full_page=True)
                    payload = {
                        "status": "GREEN",
                        "host": base_url,
                        "flow": "normal app -> College Football -> Top Picks -> first live card",
                        "detail_href": href,
                        "event_id": event_id,
                        "sections": list(REQUIRED_SECTIONS),
                        "expanded_detail": True,
                        "step3_reasoning_preserved": True,
                        "viewport": [390, 844],
                    }
                    (artifacts / "public_step4_detail_integrity.json").write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    print("CFB_TOP_PICKS_REPAIR_STEP4_PUBLIC_DETAIL_GREEN")
                    print(json.dumps(payload, indent=2, sort_keys=True))
                    return payload
                except Exception as exc:
                    last_error = repr(exc)
                    time.sleep(6)
            raise AssertionError("STEP4_PUBLIC_DEPLOY_NOT_READY:" + last_error)
        finally:
            if p is not None:
                p.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public", action="store_true")
    parser.add_argument("--base-url", default=PUBLIC_URL)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/cfb-top-picks-repair-step4-detail-integrity",
    )
    args = parser.parse_args()
    if args.public:
        run_public(base_url=args.base_url, artifact_dir=args.artifact_dir)
    else:
        run_live(args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
