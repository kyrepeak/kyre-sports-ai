"""WNBA PRA Repair V1 Step 3 — strong Page-3 data completeness certification.

GREEN + FROZEN requires the Step-3 runtime to be active on the real public
Player Intelligence route. Component-only proof is insufficient.

The verifier:
- validates the persisted MONSTER V8 execution plan;
- requires Step 3 to inherit the merged Step-2 team-identity runtime;
- preserves frozen model/market/probability/qualification/ranking behavior;
- can certify source contracts on an exact PR head without browser dependencies;
- on merged main, uses one authoritative deployment-watch run and tries multiple
  real WNBA dates/games so an unrelated Page-2 empty game does not masquerade as
  a Page-3 failure;
- never claims Page 2 is globally certified.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.execution_plan_compiler_v1 import validate_execution_plan
from devsystem.chaos_adversarial_certification_harness_v1 import (
    contract_self_test as chaos_contract_self_test,
)
import wnba_pra_repair_v1_step3_data as data

PROJECT = "WNBA PRA Repair V1"
STEP = "3/7"
BASE_MAIN_SHA = "5bdbe8548a3cc20db2100d2d6b458b49c6956521"
PUBLIC_HOST = "https://pickvault.streamlit.app"
PROOF_SELECTOR = '[data-wnba-pra-repair-v1-step3="data-completeness"]'
DEPLOYMENT_ATTEMPTS = 12
DEPLOYMENT_RETRY_SECONDS = 15.0

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py"
PLAN = ROOT / "devsystem/execution_plans/wnba-pra-repair-v1-step3-data-completeness.json"


class Step3CertificationFailure(RuntimeError):
    pass


# Source-only proof must not import browser/network dependencies.
# run_production replaces these placeholders after the frozen browser stack is installed.
BrowserQAFailure = Step3CertificationFailure
nav = None
speed9 = None


def compiled_plan() -> dict[str, Any]:
    payload = json.loads(PLAN.read_text(encoding="utf-8"))
    return validate_execution_plan(payload, observed_main_sha=BASE_MAIN_SHA)


def certify_source_contract() -> dict[str, Any]:
    overlay = OVERLAY.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    checks = {
        "runtime_active": (
            "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness "
            "import record_bootstrap_import_ms, render_app"
        ) in app,
        "step2_parent_preserved": (
            'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity"'
            in overlay
        ),
        "opponent_consumer_independent": "data.opponent_identity(game, player_team_id)" in overlay,
        "recent_form_handoff": (
            '"l5_pra": getter("L5_PRA")' in overlay
            and '"l10_pra": getter("L10_PRA")' in overlay
        ),
        "usage_handoff": '"projected_usage": getter("PROJ_USG")' in overlay,
        "pace_v36_reused": "matchup.matchup_factors_v36" in overlay,
        "history_opponent_repair": "_repair_history_summary" in overlay,
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
        raise Step3CertificationFailure(f"Step-3 source contract failed: {failed}")
    print("WNBA_PRA_REPAIR_V1_STEP3_SOURCE_CONTRACT_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_STEP2_PARENT_GREEN")
    return {"status": "GREEN", "checks": checks}


def certify_helpers() -> dict[str, Any]:
    game = {
        "away_team_id": 1611661317,
        "away_team": "Phoenix Mercury",
        "away_tricode": "PHX",
        "home_team_id": 1611661328,
        "home_team": "Seattle Storm",
        "home_tricode": "SEA",
    }
    opponent = data.opponent_identity(game, 1611661317)
    if opponent.get("opponent_team_key") != "seattle-storm":
        raise Step3CertificationFailure("Step-3 canonical opponent helper failed.")

    fallback = data.form_fallback({"l5_pra": 27.4, "l10_pra": 26.1})
    if fallback.get("recent5_pra") != 27.4 or fallback.get("recent10_pra") != 26.1:
        raise Step3CertificationFailure("Step-3 recent-form fallback failed.")

    usage = data.weighted_usage(20.0, 22.0, 24.0)
    if usage is None or round(usage, 4) != 21.5:
        raise Step3CertificationFailure("Step-3 usage blend contract failed.")

    return {
        "status": "GREEN",
        "opponent_key": opponent["opponent_team_key"],
        "recent5_pra": fallback["recent5_pra"],
        "recent10_pra": fallback["recent10_pra"],
        "usage_example": usage,
    }


def source_only_result() -> dict[str, Any]:
    plan = compiled_plan()
    source = certify_source_contract()
    helpers = certify_helpers()
    chaos = chaos_contract_self_test()
    if chaos.get("status") != "GREEN" or chaos.get("all_scenarios_pass") is not True:
        raise Step3CertificationFailure("MONSTER V8 chaos/adversarial certification is not GREEN.")
    result = {
        "project": PROJECT,
        "step": STEP,
        "status": "GREEN",
        "proof_kind": "EXACT_HEAD_SOURCE_CONTRACT",
        "base_main_sha": BASE_MAIN_SHA,
        "execution_plan_id": plan["plan_id"],
        "execution_plan_digest": plan["plan_digest"],
        "v8_chaos_certificate_digest": chaos["chaos_certificate_digest"],
        "source_contract": source,
        "helper_contract": helpers,
        "production_proof_complete": False,
        "green_plus_frozen_allowed": False,
    }
    print("WNBA_PRA_REPAIR_V1_STEP3_EXACT_HEAD_SOURCE_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_V8_PLAN_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP3_V8_CHAOS_GREEN")
    return result


def _true(marker, attr: str) -> bool:
    return str(marker.get_attribute(attr) or "").strip().lower() == "true"


def _wait_game_shell(page, timeout_seconds: float = 12.0):
    started = time.monotonic()
    deadline = started + timeout_seconds
    last = ""
    while time.monotonic() < deadline:
        frame, _ = nav._find_app_frame(
            page,
            timeout_seconds=min(8.0, max(2.0, deadline - time.monotonic())),
        )
        try:
            body = nav._body(frame)
            back = frame.get_by_role("button", name="← Back to WNBA Slate", exact=True)
            if "WNBA GAME CENTER" in body.upper() and back.count() > 0:
                return frame, time.monotonic() - started
            last = body[:2000]
        except Exception:
            pass
        page.wait_for_timeout(300)
    raise BrowserQAFailure(f"Step-3 game shell did not render. body={last!r}")


def _open_player_on_date(page, route_url: str, target_date: str):
    page.goto(route_url, wait_until="domcontentloaded", timeout=120000)
    frame, slate_seconds = speed9._prime_wnba_pra_route(page, route_url)
    frame = nav._set_date_with_game(page, frame, target_date)

    game_count = nav._game_button(frame).count()
    if game_count < 1:
        raise BrowserQAFailure(f"Step-3 found no games on {target_date}.")

    failures: list[str] = []
    for index in range(game_count):
        frame, _ = nav._find_app_frame(page, timeout_seconds=8.0)
        buttons = nav._game_button(frame)
        if index >= buttons.count():
            break

        started = time.monotonic()
        buttons.nth(index).click()
        try:
            frame, _ = _wait_game_shell(page)
            game_seconds = time.monotonic() - started
            player_buttons = frame.get_by_role("button", name=re.compile(r"^Open .+ PRA →$"))
            if player_buttons.count() > 0:
                player_started = time.monotonic()
                player_buttons.first.click()
                frame, _ = nav._wait_page(page, "player", timeout_seconds=45.0)
                player_seconds = time.monotonic() - player_started
                print(f"WNBA_PRA_REPAIR_V1_STEP3_PROOF_DATE={target_date}")
                print(f"WNBA_PRA_REPAIR_V1_STEP3_PROOF_GAME_INDEX={index}")
                return frame, slate_seconds, game_seconds, player_seconds
            failures.append(f"game[{index}]:no_tappable_players")
        except Exception as exc:
            failures.append(f"game[{index}]:{type(exc).__name__}:{str(exc)[:160]}")

        try:
            frame, _ = nav._find_app_frame(page, timeout_seconds=8.0)
            back = frame.get_by_role("button", name="← Back to WNBA Slate", exact=True)
            if back.count() > 0:
                back.click()
                nav._wait_page(page, "slate", timeout_seconds=15.0)
        except Exception:
            pass

    raise BrowserQAFailure(
        f"Step-3 no reachable player on {target_date}; " + " | ".join(failures)
    )


def _candidate_dates() -> list[str]:
    values: list[str] = []
    try:
        values.append(nav._find_game_date())
    except Exception:
        pass
    for value in getattr(nav, "CERTIFIED_GAME_DATES", ()):
        text = str(value or "").strip()
        if text and text not in values:
            values.append(text)
    if not values:
        raise BrowserQAFailure("Step-3 has no candidate WNBA game dates.")
    return values


def _open_any_player(page, route_url: str):
    failures: list[str] = []
    for target_date in _candidate_dates():
        try:
            frame, slate_seconds, game_seconds, player_seconds = _open_player_on_date(
                page, route_url, target_date
            )
            return frame, target_date, slate_seconds, game_seconds, player_seconds
        except Exception as exc:
            failures.append(f"{target_date}:{type(exc).__name__}:{str(exc)[:220]}")
    raise BrowserQAFailure(
        "Step-3 could not reach any real public Player Intelligence route; "
        + " | ".join(failures)
    )


def run_production(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    # Browser stack is imported only for merged-main production proof.
    global BrowserQAFailure, nav, speed9
    from playwright.sync_api import sync_playwright
    from devsystem.browser_qa_v1 import BrowserQAFailure
    from devsystem import wnba_nav_v2_step7_public_freeze as nav
    from devsystem import wnba_pra_speed_v3_step9_final_cert as speed9

    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    plan = compiled_plan()
    source = certify_source_contract()
    helpers = certify_helpers()
    chaos = chaos_contract_self_test()
    if chaos.get("status") != "GREEN" or chaos.get("all_scenarios_pass") is not True:
        raise Step3CertificationFailure("MONSTER V8 chaos/adversarial certification is not GREEN.")

    route_url = speed9._wnba_pra_route_url(production_url)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        context = browser.new_context(viewport=nav.VIEWPORT)
        page = context.new_page()
        last_error = ""
        try:
            for attempt in range(1, DEPLOYMENT_ATTEMPTS + 1):
                try:
                    frame, target_date, slate_seconds, game_seconds, player_seconds = _open_any_player(
                        page, route_url
                    )
                    marker = frame.locator(PROOF_SELECTOR).first
                    if marker.count() < 1:
                        raise BrowserQAFailure("Step-3 deployment marker not active yet.")

                    attrs = (
                        "data-opponent-ready",
                        "data-recent5-ready",
                        "data-recent10-ready",
                        "data-usage-ready",
                        "data-pace-ready",
                        "data-history-opponent-linked",
                        "data-consumer-independent-context",
                    )
                    missing = [attr for attr in attrs if not _true(marker, attr)]
                    status = str(marker.get_attribute("data-status") or "")
                    if status != "green" or missing:
                        raise BrowserQAFailure(
                            f"Step-3 public marker blocked status={status!r} missing={missing}"
                        )

                    body = frame.locator("body").inner_text(timeout=5000)
                    stale = [
                        value
                        for value in (
                            "N/A — not exposed by read-only payload",
                            "N/A — not carried into frozen Step-3 snapshot",
                        )
                        if value in body
                    ]
                    if stale:
                        raise BrowserQAFailure(f"Step-3 stale placeholders remain: {stale}")

                    result = {
                        "project": PROJECT,
                        "step": STEP,
                        "status": "GREEN",
                        "proof_kind": "MERGED_MAIN_PRODUCTION",
                        "base_main_sha": BASE_MAIN_SHA,
                        "merged_main_sha": str(os.environ.get("GITHUB_SHA") or "").strip() or None,
                        "execution_plan_id": plan["plan_id"],
                        "execution_plan_digest": plan["plan_digest"],
                        "v8_chaos_certificate_digest": chaos["chaos_certificate_digest"],
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
                        "source_contract": source,
                        "helper_contract": helpers,
                        "upstream_page2_globally_certified": False,
                        "projection_math_changed": False,
                        "market_math_changed": False,
                        "probability_changed": False,
                        "qualification_changed": False,
                        "ranking_changed": False,
                    }
                    (artifacts / "wnba_pra_repair_v1_step3_data_completeness.json").write_text(
                        json.dumps(result, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    page.screenshot(
                        path=str(artifacts / "wnba_pra_repair_v1_step3_data_completeness.png"),
                        full_page=True,
                    )

                    print("WNBA_PRA_REPAIR_V1_STEP3_V8_PLAN_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_V8_CHAOS_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_OPPONENT_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_RECENT_FORM_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_USAGE_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_PACE_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_H2H_LINK_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_CONSUMER_INDEPENDENT_CONTEXT_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_GREEN")
                    print("WNBA_PRA_REPAIR_V1_STEP3_FROZEN")
                    return result
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    print(
                        "WNBA_PRA_REPAIR_V1_STEP3_DEPLOYMENT_WAIT "
                        f"attempt={attempt}/{DEPLOYMENT_ATTEMPTS} "
                        f"reason={last_error[:300]}"
                    )
                    if attempt >= DEPLOYMENT_ATTEMPTS:
                        break
                    time.sleep(DEPLOYMENT_RETRY_SECONDS)

            raise BrowserQAFailure(
                "Step-3 merged-main production proof never reached GREEN inside "
                f"the single authoritative deployment-watch run. last={last_error}"
            )
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/wnba-pra-repair-v1-step3-data-completeness",
    )
    args = parser.parse_args()

    if args.source_only:
        source_only_result()
        return 0

    run_production(
        production_url=args.production_url,
        artifact_dir=args.artifact_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
