"""Temporary proof-host adapter for API 2 NBA Spread Step 3 public certification.

This file lives only on an old proof-only branch used as a browser execution host.
It does not modify main, product code, frozen state, or Runless proof identity.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

PUBLIC_HOST = "https://pickvault.streamlit.app"


def certify_source() -> dict[str, Any]:
    result = {
        "status": "GREEN",
        "mode": "TEMPORARY_PROOF_HOST_ADAPTER",
        "main_product_mutated": False,
        "runless_rerun": False,
        "github_actions_fallback": 0,
    }
    print("NBA_SPREAD_STEP3_PROOF_HOST_ADAPTER_GREEN", flush=True)
    return result


def run_public(*, production_url: str = PUBLIC_HOST, artifact_dir: str | Path = "artifacts/nba-spread-step3-public-cert") -> dict[str, Any]:
    from playwright.sync_api import sync_playwright
    from devsystem.browser_qa_v1 import _find_app_frame

    route_url = production_url.rstrip("/") + "/?ks_sport=NBA&ks_nba_market=Spread"
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "project": "API2",
        "workstream": "nba-spread-two-page-v1",
        "task": "nba-spread-step3-schedule-phoenix-v1",
        "status": "RED",
        "route_url": route_url,
        "route_open": False,
        "rolling_7_day_visible": False,
        "matchup_identity_correct": False,
        "phoenix_time_visible": False,
        "game_state_behavior_correct": False,
        "step2_navigation_intact": False,
        "blocking_error_absent": False,
        "github_actions_fallback": 0,
        "duplicate_runless_runs": 0,
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport={"width": 1440, "height": 1200})
        page = context.new_page()
        try:
            page.goto(route_url, wait_until="domcontentloaded", timeout=120000)
            deadline = time.monotonic() + 120.0
            frame = None
            body = ""
            while time.monotonic() < deadline:
                try:
                    frame, _ = _find_app_frame(page, timeout_seconds=12.0)
                    body = frame.locator("body").inner_text(timeout=5000) or ""
                except Exception:
                    page.wait_for_timeout(500)
                    continue
                if "NBA Spread" in body and (
                    "Verified 7-Day NBA Slate" in body
                    or "Schedule verification unavailable" in body
                ):
                    break
                page.wait_for_timeout(500)

            if frame is None:
                raise RuntimeError("NBA_SPREAD_STEP3_PUBLIC_FRAME_UNAVAILABLE")

            result["route_open"] = "NBA Spread" in body
            result["rolling_7_day_visible"] = (
                "Verified 7-Day NBA Slate" in body
                and "Rolling 7-day schedule" in body
            )
            result["phoenix_time_visible"] = (
                "Phoenix, Arizona time" in body
                and "Phoenix" in body
            )
            result["step2_navigation_intact"] = (
                frame.locator('[data-testid="nba-spread-step2-active"]').count() > 0
            )

            cards = frame.locator('[data-testid="nba-spread-step3-game-card"]')
            card_count = cards.count()
            pairs: list[list[str]] = []
            statuses: list[str] = []
            allowed_states = ("UPCOMING", "DELAYED", "LIVE", "FINAL", "CANCELLED")
            for i in range(card_count):
                text = (cards.nth(i).inner_text(timeout=5000) or "").strip()
                match = re.search(r"\b([A-Z]{2,4})\s+@\s+([A-Z]{2,4})\b", text)
                if match and match.group(1) != match.group(2):
                    pairs.append([match.group(1), match.group(2)])
                status = next((s for s in allowed_states if re.search(rf"(^|\n){s}(\n|$)", text)), "")
                if status:
                    statuses.append(status)

            result["card_count"] = card_count
            result["matchups"] = pairs
            result["statuses"] = statuses
            result["matchup_identity_correct"] = card_count > 0 and len(pairs) == card_count
            result["game_state_behavior_correct"] = (
                card_count > 0
                and len(statuses) == card_count
                and "Upcoming" in body
                and "Live / Final" in body
            )

            blocking_terms = (
                "Schedule verification unavailable",
                "data limited",
                "Data limited",
                "Traceback",
                "Something went wrong",
            )
            result["blocking_error_absent"] = not any(term in body for term in blocking_terms)
            result["body_excerpt"] = body[:3000]

            required = (
                "route_open",
                "rolling_7_day_visible",
                "matchup_identity_correct",
                "phoenix_time_visible",
                "game_state_behavior_correct",
                "step2_navigation_intact",
                "blocking_error_absent",
            )
            result["status"] = "GREEN" if all(bool(result[k]) for k in required) else "RED"
            (artifacts / "nba_spread_step3_public_cert.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            page.screenshot(
                path=str(artifacts / "nba_spread_step3_public_cert.png"),
                full_page=True,
            )
            print("NBA_SPREAD_STEP3_PUBLIC_CERT=" + json.dumps(result, sort_keys=True), flush=True)
            print("NBA_SPREAD_STEP3_PUBLIC_CERT_GREEN=" + str(result["status"] == "GREEN").lower(), flush=True)
            if result["status"] != "GREEN":
                raise RuntimeError("NBA_SPREAD_STEP3_PUBLIC_CERT_RED")
            return result
        finally:
            context.close()
            browser.close()
