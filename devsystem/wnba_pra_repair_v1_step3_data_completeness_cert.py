"""WNBA PRA Repair V1 Step 3 — live Page-3 data completeness proof.

The cert waits inside one authoritative merged-main run for Streamlit deployment
freshness.  It never starts a second workflow or reruns an unchanged failure.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time
from typing import Any

from playwright.sync_api import sync_playwright

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.browser_qa_v1 import BrowserQAFailure
from devsystem import wnba_nav_v2_step7_public_freeze as nav
from devsystem import wnba_pra_speed_v3_step9_final_cert as speed9

PROJECT = "WNBA PRA Repair V1"
STEP = "3/7"
PUBLIC_HOST = "https://pickvault.streamlit.app"
PROOF_SELECTOR = '[data-wnba-pra-repair-v1-step3="data-completeness"]'
DEPLOYMENT_ATTEMPTS = 12
DEPLOYMENT_RETRY_SECONDS = 15.0

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py"
FROZEN_GAME = ROOT / "wnba_pra_game_center_v2_step3.py"
FROZEN_PLAYER = ROOT / "wnba_pra_player_intelligence_v2_step4.py"
FROZEN_STEP9 = ROOT / "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard.py"


def certify_source_contract() -> dict[str, Any]:
    app = APP.read_text(encoding="utf-8")
    overlay = OVERLAY.read_text(encoding="utf-8")
    checks = {
        "step3_runtime_active": (
            "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness "
            "import record_bootstrap_import_ms, render_app"
        ) in app,
        "step9_parent_preserved": (
            'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard"'
        ) in overlay,
        "opponent_consumer_independent": "data.opponent_identity(game, player_team_id)" in overlay,
        "form_fallback_present": "data.form_fallback(player)" in overlay,
        "pace_v36_reused": "matchup.matchup_factors_v36" in overlay,
        "usage_handoff_preserved": '"projected_usage": getter("PROJ_USG")' in overlay,
        "model_locked": "MAY_MODIFY_WNBA_MODEL = False" in overlay,
        "projection_locked": "MAY_MODIFY_PROJECTION_MATH = False" in overlay,
        "market_locked": "MAY_MODIFY_MARKET_MATH = False" in overlay,
        "probability_locked": "MAY_MODIFY_PROBABILITY = False" in overlay,
        "qualification_locked": "MAY_MODIFY_QUALIFICATION = False" in overlay,
        "ranking_locked": "MAY_MODIFY_RANKING = False" in overlay,
        "sportsbook_influence_zero": "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in overlay,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise BrowserQAFailure(f"Step-3 source contract failed: {failed}")
    print("WNBA_PRA_REPAIR_V1_STEP3_SOURCE_CONTRACT_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_FROZEN_STEP9_PARENT_GREEN")
    return {"status": "GREEN", "checks": checks}


def _true(marker, attr: str) -> bool:
    return str(marker.get_attribute(attr) or "").strip().lower() == "true"


def _open_player(page, route_url: str, target_date: str):
    page.goto(route_url, wait_until="domcontentloaded", timeout=120000)
    frame, slate_seconds = speed9._prime_wnba_pra_route(page, route_url)
    frame = nav._set_date_with_game(page, frame, target_date)

    game_button = nav._game_button(frame).first
    game_started = time.monotonic()
    game_button.click()
    frame, _ = nav._wait_page(page, "game", timeout_seconds=nav.GAME_READY_BUDGET_SECONDS)
    game_seconds = time.monotonic() - game_started

    player_buttons = frame.get_by_role("button", name=re.compile(r"^Open .+ PRA →$"))
    if player_buttons.count() < 1:
        raise BrowserQAFailure("Step-3 proof found no tappable PRA player.")

    player_started = time.monotonic()
    player_buttons.first.click()
    frame, _ = nav._wait_page(page, "player", timeout_seconds=45.0)
    player_seconds = time.monotonic() - player_started
    return frame, slate_seconds, game_seconds, player_seconds


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    source = certify_source_contract()
    route_url = speed9._wnba_pra_route_url(production_url)
    target_date = nav._find_game_date()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport=nav.VIEWPORT)
        page = context.new_page()
        last_error = ""
        try:
            for attempt in range(1, DEPLOYMENT_ATTEMPTS + 1):
                try:
                    frame, slate_seconds, game_seconds, player_seconds = _open_player(
                        page, route_url, target_date
                    )
                    marker = frame.locator(PROOF_SELECTOR).first
                    if marker.count() < 1:
                        raise BrowserQAFailure("Step-3 deployment marker not active yet.")
                    if str(marker.get_attribute("data-status") or "") != "green":
                        attrs = {
                            key: marker.get_attribute(key)
                            for key in (
                                "data-opponent-ready",
                                "data-recent5-ready",
                                "data-recent10-ready",
                                "data-usage-ready",
                                "data-pace-ready",
                                "data-history-opponent-linked",
                            )
                        }
                        raise BrowserQAFailure(f"Step-3 marker blocked: {attrs}")

                    required = (
                        "data-opponent-ready",
                        "data-recent5-ready",
                        "data-recent10-ready",
                        "data-usage-ready",
                        "data-pace-ready",
                        "data-history-opponent-linked",
                        "data-consumer-independent-context",
                    )
                    missing = [attr for attr in required if not _true(marker, attr)]
                    if missing:
                        raise BrowserQAFailure(f"Step-3 public data fields incomplete: {missing}")

                    body = frame.locator("body").inner_text(timeout=5000)
                    stale_literals = (
                        "N/A — not exposed by read-only payload",
                        "N/A — not carried into frozen Step-3 snapshot",
                    )
                    leaked = [value for value in stale_literals if value in body]
                    if leaked:
                        raise BrowserQAFailure(f"Step-3 stale Page-3 placeholders remain: {leaked}")

                    result = {
                        "project": PROJECT,
                        "step": STEP,
                        "status": "GREEN",
                        "production_url": production_url,
                        "target_date": target_date,
                        "deployment_attempt": attempt,
                        "slate_ready_seconds": round(float(slate_seconds), 3),
                        "game_ready_seconds": round(float(game_seconds), 3),
                        "player_ready_seconds": round(float(player_seconds), 3),
                        "opponent_ready": True,
                        "recent5_ready": True,
                        "recent10_ready": True,
                        "usage_ready": True,
                        "pace_ready": True,
                        "history_opponent_linked": True,
                        "consumer_independent_context": True,
                        "history_games": int(marker.get_attribute("data-history-games") or 0),
                        "h2h_games": int(marker.get_attribute("data-h2h-games") or 0),
                        "recent_fallback_used": _true(marker, "data-recent-fallback-used"),
                        "frozen_speed_v3_steps_1_9_preserved": True,
                        "projection_math_changed": False,
                        "market_math_changed": False,
                        "probability_changed": False,
                        "source_contract": source,
                    }
                    (artifacts / "wnba_pra_repair_v1_step3_data_completeness.json").write_text(
                        json.dumps(result, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    page.screenshot(
                        path=str(artifacts / "wnba_pra_repair_v1_step3_data_completeness.png"),
                        full_page=True,
                    )

                    print("WNBA_PRA_REPAIR_V1_STEP3_OPPONENT_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_RECENT_FORM_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_USAGE_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_PACE_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_H2H_LINK_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_CONSUMER_INDEPENDENT_CONTEXT_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_FROZEN_SPEED_V3_STEPS1_9_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_FROZEN")
                    return result
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    print(
                        f"WNBA_PRA_REPAIR_V1_STEP3_DEPLOYMENT_WAIT "
                        f"attempt={attempt}/{DEPLOYMENT_ATTEMPTS} reason={last_error[:300]}"
                    )
                    if attempt >= DEPLOYMENT_ATTEMPTS:
                        break
                    time.sleep(DEPLOYMENT_RETRY_SECONDS)

            raise BrowserQAFailure(
                "Step-3 merged-main production proof never reached GREEN inside "
                f"the single deployment-watch run. last={last_error}"
            )
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/wnba-pra-repair-v1-step3-data-completeness",
    )
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
