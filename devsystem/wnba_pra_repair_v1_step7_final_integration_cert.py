from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
ENGINE = ROOT / "wnba_pra_repair_v1_step7_final_integration.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration.py"
STEP6 = ROOT / "wnba_pra_repair_v1_step6_completeness_sweep.py"
STEP5_ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step5_decision_fallback.py"


def main() -> int:
    app = APP.read_text(encoding="utf-8")
    engine = ENGINE.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    step6 = STEP6.read_text(encoding="utf-8")
    step5_router = STEP5_ROUTER.read_text(encoding="utf-8")

    checks = {
        "engine_exists": ENGINE.exists(),
        "router_exists": ROUTER.exists(),
        "step6_dependency_exists": STEP6.exists(),
        "frozen_parent_exists": STEP5_ROUTER.exists(),
        "app_runtime_marker": "WNBA_PRA_REPAIR_V1_STEP7_FINAL_INTEGRATION_RUNTIME" in app,
        "app_runtime_active": (
            "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration "
            "import record_bootstrap_import_ms, render_app"
        ) in app,
        "parent_chain_step5": (
            "streamlit_memory_lazy_router_wnba_pra_repair_v1_step5_decision_fallback as frozen_parent"
            in router
        ),
        "step6_guard_reused": "wnba_pra_repair_v1_step6_completeness_sweep as step6" in router,
        "game_guard": "def guarded_game_renderer" in router,
        "player_card_guard": "def guarded_player_card" in router,
        "player_guard": "def guarded_player_renderer" in router,
        "final_card_guard": "def guarded_final_card_renderer" in router,
        "runtime_restores": all(
            token in router
            for token in (
                "game_center.render_game_center = original_game_renderer",
                "game_center._render_player_card = original_player_card_renderer",
                "player_intelligence.render_player_intelligence = original_player_renderer",
                "step5_engine.render_step5_final_card = original_final_card_renderer",
            )
        ),
        "no_new_network": all(token not in router for token in ("KyreWNBAAPIClient", "requests.", "httpx.")),
        "pure_engine_no_streamlit": "import streamlit" not in engine,
        "pure_engine_no_network": all(token not in engine for token in ("KyreWNBAAPIClient", "requests.", "httpx.")),
        "step6_still_verification_only": "Verification-only" in step6,
        "step5_still_parent_runtime": "def render_app" in step5_router,
        "math_frozen": all(
            token in router
            for token in (
                "MAY_MODIFY_WNBA_MODEL = False",
                "MAY_MODIFY_PROJECTION_MATH = False",
                "MAY_MODIFY_MARKET_MATH = False",
                "MAY_MODIFY_PROBABILITY = False",
                "MAY_MODIFY_QUALIFICATION = False",
                "MAY_MODIFY_RANKING = False",
                "MAY_MODIFY_OTHER_SPORTS = False",
                "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
            )
        ),
    }
    ok = all(checks.values())
    print(json.dumps({"status": "GREEN" if ok else "FAIL", "checks": checks}, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
