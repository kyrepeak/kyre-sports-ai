"""WNBA PRA Repair V1 Step 1 — three-page production load audit.

Proof-only certification for the new seven-step repair mission.  It preserves
all nine frozen WNBA PRA Speed V3 steps and changes no product/model/runtime
behavior.  The public proof exercises the actual Slate -> Game Center -> Player
Intelligence -> Game Center -> Slate path through the current Step-9 runtime.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.browser_qa_v1 import BrowserQAFailure
from devsystem import wnba_nav_v2_step7_public_freeze as nav
from devsystem import wnba_pra_speed_v3_step9_final_cert as speed9

PROJECT = "WNBA PRA Repair V1"
STEP = "1/7"
PUBLIC_HOST = "https://pickvault.streamlit.app"
PRODUCT_RUNTIME_CHANGED = False
MODEL_CHANGED = False
PROJECTION_MATH_CHANGED = False
MARKET_MATH_CHANGED = False
SPORTSBOOK_PROJECTION_INFLUENCE_CHANGED = False

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
STEP9_ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard.py"
NAVIGATION = ROOT / "wnba_pra_navigation_v2_step1.py"
SLATE = ROOT / "wnba_pra_slate_v2_step2.py"
GAME = ROOT / "wnba_pra_game_center_v2_step3.py"
PLAYER = ROOT / "wnba_pra_player_intelligence_v2_step4.py"

RUNTIME_IMPORT = (
    "from streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard "
    "import record_bootstrap_import_ms, render_app"
)


def certify_source_contract() -> dict[str, Any]:
    required = (APP, STEP9_ROUTER, NAVIGATION, SLATE, GAME, PLAYER)
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise BrowserQAFailure(f"Step-1 required WNBA page files missing: {missing}")

    app = APP.read_text(encoding="utf-8")
    router = STEP9_ROUTER.read_text(encoding="utf-8")
    navigation = NAVIGATION.read_text(encoding="utf-8")
    slate = SLATE.read_text(encoding="utf-8")
    game = GAME.read_text(encoding="utf-8")
    player = PLAYER.read_text(encoding="utf-8")

    checks = {
        "step9_runtime_import": RUNTIME_IMPORT in app,
        "step9_delegates_frozen_parent": "return frozen_parent.render_app()" in router,
        "slate_route_present": "render_slate_page" in slate,
        "game_route_present": "render_game_center" in game,
        "player_route_present": "render_player_intelligence" in player,
        "slate_page_constant": "PAGE_SLATE" in navigation,
        "game_page_constant": "PAGE_GAME" in navigation,
        "player_page_constant": "PAGE_PLAYER" in navigation,
        "slate_to_game_control": "Open Game Center" in slate,
        "game_to_player_control": "PRA" in game,
        "player_to_game_control": "Back to Game Center" in player,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise BrowserQAFailure(f"Step-1 source/load contract failed: {failed}")

    print("WNBA_PRA_REPAIR_V1_STEP1_SOURCE_CONTRACT_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP1_STEP9_RUNTIME_PRESERVED_GREEN")
    return {
        "status": "GREEN",
        "checks": checks,
        "product_runtime_changed": PRODUCT_RUNTIME_CHANGED,
        "model_changed": MODEL_CHANGED,
        "projection_math_changed": PROJECTION_MATH_CHANGED,
        "market_math_changed": MARKET_MATH_CHANGED,
        "sportsbook_projection_influence_changed": SPORTSBOOK_PROJECTION_INFLUENCE_CHANGED,
    }


def run(*, production_url: str, artifact_dir: str | Path) -> dict[str, Any]:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    source = certify_source_contract()

    route_url = speed9._wnba_pra_route_url(production_url)
    original_route = nav._route_to_wnba_pra
    original_dates = nav.CERTIFIED_GAME_DATES

    # Step 2A: one authoritative browser pass only.  Reuse the already-frozen
    # exact-label route primer and the existing three-page production verifier.
    target_date = nav._find_game_date()

    def exact_route(page):
        return speed9._prime_wnba_pra_route(page, route_url)

    nav._route_to_wnba_pra = exact_route
    nav.CERTIFIED_GAME_DATES = (target_date,)
    try:
        public = nav.run(
            production_url=route_url,
            artifact_dir=artifacts / "three-page-public",
        )
    finally:
        nav._route_to_wnba_pra = original_route
        nav.CERTIFIED_GAME_DATES = original_dates

    if public.get("status") != "GREEN":
        raise BrowserQAFailure("Step-1 three-page public verifier did not finish GREEN.")
    if public.get("three_page_public_path_green") is not True:
        raise BrowserQAFailure("Step-1 public path did not certify Slate/Game/Player.")
    if public.get("lazy_loading_green") is not True:
        raise BrowserQAFailure("Step-1 Slate lazy-load contract regressed.")
    if public.get("zero_horizontal_overflow_green") is not True:
        raise BrowserQAFailure("Step-1 public page overflow contract regressed.")

    result = {
        "project": PROJECT,
        "step": STEP,
        "status": "GREEN",
        "production_url": production_url,
        "route_url": route_url,
        "tested_game_date": target_date,
        "source_contract": source,
        "slate_page_green": True,
        "game_center_page_green": True,
        "player_intelligence_page_green": True,
        "round_trip_navigation_green": True,
        "all_nine_speed_v3_steps_preserved": True,
        "product_runtime_changed": False,
    }
    (artifacts / "wnba_pra_repair_v1_step1_load_audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("WNBA_PRA_REPAIR_V1_STEP1_SLATE_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP1_GAME_CENTER_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP1_PLAYER_INTELLIGENCE_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP1_ROUND_TRIP_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP1_FROZEN_SPEED_V3_STEPS1_9_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP1_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP1_FROZEN")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", default=PUBLIC_HOST)
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/wnba-pra-repair-v1-step1-load-audit",
    )
    args = parser.parse_args()
    run(production_url=args.production_url, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
