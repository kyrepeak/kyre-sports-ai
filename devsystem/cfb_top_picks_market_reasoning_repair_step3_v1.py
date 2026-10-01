"""CFB Top Picks Repair Step 3 — live Market-Aware Football Reasoning cert.

This is an additive verifier only. It does not modify any Top Picks model,
ranking, probability, selection, page, router, sportsbook input, or API 2
behavior. The repair closes a proof gap: the legacy Step-6 fixture cert and
Step-9 full-slate cert could pass without requiring the live reasoning block to
be READY for every ranked pick.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time
from typing import Any, Mapping
from urllib.parse import urlencode

import cfb_top_picks_details_v5 as details
import cfb_top_picks_engine_v1 as engine
import cfb_top_picks_market_reasoning_v1 as reasoning
import cfb_top_picks_page_v9 as page

MODEL_VERSION = "CFB TOP PICKS REPAIR STEP 3 • MARKET-AWARE REASONING LIVE CERT"
MISSION_STEP = "3/5"
PUBLIC_URL = "https://pickvault.streamlit.app"
API2_USED = False
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
MARKET_REASONING_PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SELECTION = False
READY_SIGNAL_STATUSES = {"VERIFIED", "PARTIAL", "VERIFIED_NO_HISTORY"}
HISTORY_SIGNAL_BY_MARKET = {
    "OVER/UNDER": "history_total_context",
    "SPREAD": "history_margin_context",
    "MONEYLINE": "history_winner_context",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _validate_reasoning(row: Mapping[str, Any], detail: Mapping[str, Any]) -> dict[str, Any]:
    rank = int(row.get("rank") or 0)
    market = _clean(row.get("market")).upper()
    if market not in reasoning.REQUIRED_SIGNALS:
        raise AssertionError(f"STEP3_UNSUPPORTED_MARKET:{rank}:{market}")

    block = detail.get("market_reasoning") or {}
    block_status = _clean(block.get("status")).upper()
    if block_status not in {"READY", "PARTIAL"}:
        raise AssertionError(
            f"STEP3_REASONING_NOT_USABLE:{rank}:{market}:{block.get('status')}"
        )
    if _clean(block.get("market")).upper() != market:
        raise AssertionError(
            f"STEP3_MARKET_IDENTITY:{rank}:{market}:{block.get('market')}"
        )

    expected = list(reasoning.REQUIRED_SIGNALS[market])
    required = list(block.get("required_signals") or [])
    signals = block.get("signals") or {}
    if required != expected:
        raise AssertionError(f"STEP3_REQUIRED_SIGNAL_DRIFT:{rank}:{market}")
    if set(signals) != set(expected):
        raise AssertionError(f"STEP3_SIGNAL_SET_DRIFT:{rank}:{market}")

    history_key = HISTORY_SIGNAL_BY_MARKET[market]
    history_conflict = False
    for key in expected:
        item = signals.get(key) or {}
        status = _clean(item.get("status")).upper()
        if key == history_key and status == "SOURCE_CONFLICT_REVIEW":
            history_conflict = True
        elif status not in READY_SIGNAL_STATUSES:
            raise AssertionError(
                f"STEP3_SIGNAL_NOT_READY:{rank}:{market}:{key}:{status}"
            )
        text = _clean(item.get("text"))
        if len(text) < 20:
            raise AssertionError(f"STEP3_SIGNAL_TEXT:{rank}:{market}:{key}")
        if not _clean(item.get("observed_at")):
            raise AssertionError(f"STEP3_SIGNAL_FRESHNESS:{rank}:{market}:{key}")
        if not list(item.get("sources") or []):
            raise AssertionError(f"STEP3_SIGNAL_SOURCE:{rank}:{market}:{key}")

    expected_block_status = "PARTIAL" if history_conflict else "READY"
    if block_status != expected_block_status:
        raise AssertionError(
            f"STEP3_REASONING_STATUS_TRUTH:{rank}:{market}:"
            f"{block_status}:{expected_block_status}"
        )

    if float(block.get("projection_weight") or 0.0) != 0.0:
        raise AssertionError(f"STEP3_PROJECTION_WEIGHT:{rank}")
    if float(block.get("sportsbook_projection_weight") or 0.0) != 0.0:
        raise AssertionError(f"STEP3_SPORTSBOOK_WEIGHT:{rank}")
    if block.get("may_modify_projection") is not False:
        raise AssertionError(f"STEP3_PROJECTION_FIREWALL:{rank}")
    if block.get("may_modify_probability") is not False:
        raise AssertionError(f"STEP3_PROBABILITY_FIREWALL:{rank}")
    if block.get("may_modify_ranking") is not False:
        raise AssertionError(f"STEP3_RANKING_FIREWALL:{rank}")
    if block.get("may_modify_selection") is not False:
        raise AssertionError(f"STEP3_SELECTION_FIREWALL:{rank}")
    if block.get("api2_used") is not False:
        raise AssertionError(f"STEP3_API2_FIREWALL:{rank}")

    summary = _clean(block.get("summary"))
    if len(summary) < 20:
        raise AssertionError(f"STEP3_SUMMARY:{rank}")

    html = page._detail_card(dict(row), dict(detail))
    required_tokens = (
        "Market-Aware Football Reasoning",
        f'data-testid="cfb-top-picks-market-reasoning-{rank}"',
        f'data-reasoning-status="{expected_block_status}"',
        f'data-market="{market}"',
    )
    for token in required_tokens:
        if token not in html:
            raise AssertionError(f"STEP3_FINAL_V9_SURFACE:{rank}:{token}")

    return {
        "rank": rank,
        "event_id": _clean(row.get("event_id")),
        "market": market,
        "status": expected_block_status,
        "history_source_conflict_disclosed": history_conflict,
        "required_signal_count": len(expected),
        "summary": summary,
    }


def run_live(
    artifact_dir: str | Path = "artifacts/cfb-top-picks-repair-step3-market-reasoning"
) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    picks, diag = engine.build_top_picks(limit=10)
    if len(picks) != 10:
        raise AssertionError(f"STEP3_TOP10_COUNT:{len(picks)}")
    ranks = [int(row.get("rank") or 0) for row in picks]
    if ranks != list(range(1, 11)):
        raise AssertionError(f"STEP3_RANK_ORDER:{ranks}")

    slate_day = _clean(diag.get("slate_date")) or "Today"

    def build(row: Mapping[str, Any]):
        return row, details.build_pick_detail(row, slate_day)

    resolved = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(build, row) for row in picks]
        for future in as_completed(futures):
            resolved.append(future.result())

    certified = [
        _validate_reasoning(row, detail)
        for row, detail in sorted(
            resolved, key=lambda pair: int(pair[0].get("rank") or 99)
        )
    ]
    if len(certified) != 10:
        raise AssertionError(f"STEP3_CERTIFIED_COUNT:{len(certified)}")

    markets = sorted({item["market"] for item in certified})
    payload = {
        "status": "GREEN",
        "mission_step": MISSION_STEP,
        "slate_day": slate_day,
        "ranked_picks_certified": 10,
        "markets_observed": markets,
        "all_reasoning_usable": True,
        "history_conflict_policy": "allowed only on dedicated history signal and must remain PARTIAL",
        "projection_changed": False,
        "probability_changed": False,
        "ranking_changed": False,
        "selection_changed": False,
        "sportsbook_projection_weight": 0.0,
        "api2_used": False,
        "picks": certified,
    }
    (artifacts / "live_reasoning_10_of_10.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("CFB_TOP_PICKS_REPAIR_STEP3_MARKET_REASONING_10_OF_10_GREEN")
    print("CFB_TOP_PICKS_REPAIR_STEP3_FINAL_V9_REASONING_SURFACE_GREEN")
    print("CFB_TOP_PICKS_REPAIR_STEP3_PROJECTION_FIREWALL_GREEN")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def run_public(
    *,
    base_url: str = PUBLIC_URL,
    artifact_dir: str | Path = "artifacts/cfb-top-picks-repair-step3-market-reasoning",
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
                        raise AssertionError("STEP3_PUBLIC_DETAIL_LINK_MISSING")

                    href = _clean(detail_link.get_attribute("href"))
                    detail_link.click(timeout=15000)

                    reasoning_loc = None
                    reasoning_frame = None
                    reasoning_deadline = time.monotonic() + 180.0
                    while time.monotonic() < reasoning_deadline:
                        for frame in p.frames:
                            try:
                                loc = frame.locator(
                                    '[data-testid^="cfb-top-picks-market-reasoning-"]'
                                    '[data-reasoning-status]'
                                )
                                if loc.count() == 1 and loc.first.is_visible():
                                    reasoning_loc = loc.first
                                    reasoning_frame = frame
                                    break
                            except Exception:
                                pass
                        if reasoning_loc is not None:
                            break
                        p.wait_for_timeout(500)

                    if reasoning_loc is None or reasoning_frame is None:
                        raise AssertionError("STEP3_PUBLIC_REASONING_NOT_READY")

                    status = _clean(
                        reasoning_loc.get_attribute("data-reasoning-status")
                    ).upper()
                    market = _clean(reasoning_loc.get_attribute("data-market")).upper()
                    text = _clean(reasoning_loc.inner_text())
                    if status not in {"READY", "PARTIAL"}:
                        raise AssertionError(f"STEP3_PUBLIC_STATUS:{status}")
                    if market not in reasoning.REQUIRED_SIGNALS:
                        raise AssertionError(f"STEP3_PUBLIC_MARKET:{market}")
                    if "Market-Aware Football Reasoning" not in text:
                        raise AssertionError("STEP3_PUBLIC_HEADING_MISSING")

                    body = _clean(
                        reasoning_frame.locator("body").inner_text(timeout=5000)
                    )
                    if "CFB_TOP_PICKS_RESEARCH_V2_STEP9_FULL_SLATE_CERTIFIED" not in body:
                        raise AssertionError("STEP3_PUBLIC_V9_MARKER_MISSING")

                    screenshot = artifacts / "public_reasoning_390_green.png"
                    p.screenshot(path=str(screenshot), full_page=True)
                    payload = {
                        "status": "GREEN",
                        "host": base_url,
                        "flow": "normal app -> College Football -> Top Picks -> first live card",
                        "detail_href": href,
                        "market": market,
                        "reasoning_status": status,
                        "viewport": [390, 844],
                        "v9_marker": True,
                    }
                    (artifacts / "public_reasoning.json").write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    print("CFB_TOP_PICKS_REPAIR_STEP3_PUBLIC_REASONING_GREEN")
                    print(json.dumps(payload, indent=2, sort_keys=True))
                    return payload
                except Exception as exc:
                    last_error = repr(exc)
                    time.sleep(6)
            raise AssertionError(
                "STEP3_PUBLIC_DEPLOY_NOT_READY:" + last_error
            )
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
        default="artifacts/cfb-top-picks-repair-step3-market-reasoning",
    )
    args = parser.parse_args()
    if args.public:
        run_public(base_url=args.base_url, artifact_dir=args.artifact_dir)
    else:
        run_live(args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
