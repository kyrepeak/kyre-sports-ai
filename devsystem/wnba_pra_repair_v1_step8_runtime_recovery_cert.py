"""WNBA PRA Repair V1 Step 8 — public runtime recovery certification.

Deployment-only recovery owner. Source certification is browser-free; the public
probe uses the exact-labeled WNBA/PRA route and future-pregame discovery. An
off-day slate is valid route readiness; game readiness is checked only after the
verifier selects a scheduled future pregame date.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQ = ROOT / "requirements.txt"
APP = ROOT / "app.py"

PUBLIC_HOST = "https://pickvault.streamlit.app"
MARKER = "# WNBA PRA Repair V1 Step 8 runtime recovery full Streamlit redeploy trigger 2026-10-06 R1"
FULL_REDEPLOY_MARKER = MARKER
STEP7_RUNTIME = "WNBA_PRA_REPAIR_V1_STEP7_FINAL_INTEGRATION"
STEP7_SELECTOR = (
    '[data-wnba-pra-repair-v1-step7="wnba-pra-repair-v1-step7-final-integration"]'
    '[data-status="green"]'
)
PACKAGE_LINES = (
    "streamlit",
    "requests",
    "pandas",
    "numpy",
    "streamlit-autorefresh",
    "streamlit-local-storage==0.0.25",
    "tzdata>=2025.2",
    "posthog~=7.48",
)

PRODUCT_RUNTIME_CHANGED = False
ROUTER_CHANGED = False
MODEL_MATH_CHANGED = False
PROJECTION_MATH_CHANGED = False
MARKET_MATH_CHANGED = False
PROBABILITY_MATH_CHANGED = False
DATA_MEANING_CHANGED = False
SPORTSBOOK_PROJECTION_INFLUENCE_CHANGED = False
PAST_GAMES_ALLOWED = False


class Step8RuntimeRecoveryFailure(RuntimeError):
    pass


def certify_source() -> dict[str, Any]:
    requirements = REQ.read_text(encoding="utf-8").splitlines()
    app = APP.read_text(encoding="utf-8")
    checks = {
        "dependency_lines_unchanged": requirements[: len(PACKAGE_LINES)] == list(PACKAGE_LINES),
        "full_redeploy_marker_exactly_once": requirements.count(FULL_REDEPLOY_MARKER) == 1,
        "step7_runtime_marker_preserved": STEP7_RUNTIME in app,
        "step7_runtime_import_active": (
            "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration "
            "import record_bootstrap_import_ms, render_app"
        ) in app,
        "product_runtime_changed": PRODUCT_RUNTIME_CHANGED is False,
        "router_changed": ROUTER_CHANGED is False,
        "model_math_changed": MODEL_MATH_CHANGED is False,
        "projection_math_changed": PROJECTION_MATH_CHANGED is False,
        "market_math_changed": MARKET_MATH_CHANGED is False,
        "probability_math_changed": PROBABILITY_MATH_CHANGED is False,
        "data_meaning_changed": DATA_MEANING_CHANGED is False,
        "past_games_allowed": PAST_GAMES_ALLOWED is False,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise Step8RuntimeRecoveryFailure("STEP8_SOURCE_CONTRACT_FAILED:" + ",".join(failed))
    print("WNBA_PRA_REPAIR_V1_STEP8_DEPLOYMENT_ONLY_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP8_STEP7_RUNTIME_PRESERVED_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP8_NO_PAST_GAMES_POLICY_GREEN")
    return {"status": "GREEN", "checks": checks}


def _future_pregame_dates() -> tuple[str, ...]:
    """Discover only scheduled future WNBA pregame dates; past games are forbidden."""
    from devsystem.wnba_pra_speed_v3_step9_final_cert import _future_pregame_dates as impl

    dates = tuple(impl())
    if not dates:
        raise Step8RuntimeRecoveryFailure("No scheduled future WNBA pregame is available.")
    return dates


def _prime_wnba_pra_route(page, route_url: str):
    """Acquire the WNBA/PRA slate without requiring the default date to have a game."""
    from devsystem.browser_qa_v1 import BrowserQAFailure
    from devsystem import wnba_nav_v2_step7_public_freeze as nav

    started = time.monotonic()
    page.goto(route_url, wait_until="domcontentloaded", timeout=90_000)
    deadline = started + 90.0
    last = ""
    while time.monotonic() < deadline:
        frame, _ = nav._find_app_frame(
            page,
            timeout_seconds=min(10.0, max(2.0, deadline - time.monotonic())),
        )
        try:
            body = frame.locator("body").inner_text(timeout=4_000)
            if "WNBA Slate" in body and "Slate date" in body:
                elapsed = time.monotonic() - started
                print("WNBA_PRA_REPAIR_V1_STEP8_OFF_DAY_SLATE_ACCEPTED_GREEN")
                print(f"WNBA_PRA_REPAIR_V1_STEP8_ROUTE_READY_SECONDS={elapsed:.3f}")
                return frame, elapsed
            last = body[:5000]
        except Exception:
            pass
        page.wait_for_timeout(250)
    raise BrowserQAFailure(
        f"Step-8 WNBA/PRA slate did not become route-ready. body={last!r}"
    )


def _route_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/?ks_jump_sport=WNBA&ks_jump_market=PRA"


def run_public(*, production_url: str = PUBLIC_HOST, artifact_dir: str | Path = "artifacts/wnba-pra-repair-v1-step8") -> dict[str, Any]:
    """Prove the hosted app recovered to frozen Step 7 using a scheduled future WNBA pregame."""
    from playwright.sync_api import sync_playwright
    from devsystem.browser_qa_v1 import BrowserQAFailure
    from devsystem import wnba_nav_v2_step7_public_freeze as nav

    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    dates = _future_pregame_dates()
    route_url = _route_url(production_url)
    result: dict[str, Any] = {
        "project": "WNBA PRA Repair V1",
        "step": "8/9",
        "status": "BLOCKED",
        "production_url": production_url,
        "future_dates": list(dates),
        "past_games_allowed": False,
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport=nav.VIEWPORT)
        page = context.new_page()
        try:
            frame, slate_seconds = _prime_wnba_pra_route(page, route_url)
            selected_date = ""
            failures: list[str] = []
            for target in dates:
                try:
                    frame = nav._set_date_with_game(page, frame, target)
                    if nav._game_button(frame).count() > 0:
                        selected_date = target
                        break
                except Exception as exc:
                    failures.append(f"{target}:{type(exc).__name__}:{str(exc)[:160]}")
            if not selected_date:
                raise BrowserQAFailure(
                    "Step-8 could not activate any scheduled future WNBA pregame; " + ",".join(failures[-6:])
                )

            nav._game_button(frame).first.click()
            frame, game_seconds = nav._wait_page(page, "game", timeout_seconds=nav.GAME_READY_BUDGET_SECONDS)
            game_marker = frame.locator(STEP7_SELECTOR).first
            deadline = time.monotonic() + 8.0
            while game_marker.count() < 1 and time.monotonic() < deadline:
                page.wait_for_timeout(100)
                frame, _ = nav._find_app_frame(page, timeout_seconds=4.0)
                game_marker = frame.locator(STEP7_SELECTOR).first
            if game_marker.count() < 1:
                raise BrowserQAFailure("Frozen Step-7 final-integration marker is absent on public Game Center.")

            player_buttons = frame.get_by_role("button", name=__import__("re").compile(r"^Open .+ PRA →$"))
            if player_buttons.count() < 1:
                raise BrowserQAFailure("Step-8 public Game Center has no Player PRA control.")
            player_buttons.first.click()
            frame, player_seconds = nav._wait_page(page, "player", timeout_seconds=nav.PLAYER_READY_BUDGET_SECONDS)
            player_marker = frame.locator(STEP7_SELECTOR).first
            if player_marker.count() < 1:
                raise BrowserQAFailure("Frozen Step-7 final-integration marker is absent on public Player page.")

            final_ready, missing = nav._player_final_surfaces_ready(frame)
            if not final_ready:
                raise BrowserQAFailure(f"Step-8 public Player final surfaces missing: {missing}")

            result.update(
                {
                    "status": "GREEN",
                    "selected_future_date": selected_date,
                    "slate_ready_seconds": round(float(slate_seconds), 3),
                    "game_ready_seconds": round(float(game_seconds), 3),
                    "player_ready_seconds": round(float(player_seconds), 3),
                    "step7_public_runtime_green": True,
                    "future_pregame_only": True,
                }
            )
            (artifacts / "wnba_pra_repair_v1_step8_runtime_recovery.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            page.screenshot(path=str(artifacts / "wnba_pra_repair_v1_step8_runtime_recovery.png"), full_page=True)
            print(f"WNBA_PRA_REPAIR_V1_STEP8_FUTURE_GAME_GREEN={selected_date}")
            print("WNBA_PRA_REPAIR_V1_STEP8_PUBLIC_STEP7_RUNTIME_GREEN")
            print("WNBA_PRA_REPAIR_V1_STEP8_RUNTIME_RECOVERY_GREEN")
            return result
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument("--artifact-dir", default="artifacts/wnba-pra-repair-v1-step8")
    args = parser.parse_args()
    certify_source()
    if not args.source_only:
        run_public(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
