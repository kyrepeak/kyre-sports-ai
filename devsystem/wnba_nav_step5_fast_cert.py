"""Fast exact-head certification for WNBA Navigation V2 Step 5."""
from __future__ import annotations

import ast
import py_compile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PERF = ROOT / "wnba_pra_performance_v2_step5.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_nav_v2_step5.py"
STEP2 = ROOT / "wnba_pra_slate_v2_step2.py"
STEP3 = ROOT / "wnba_pra_game_center_v2_step3.py"
STEP4 = ROOT / "wnba_pra_player_intelligence_v2_step4.py"
APP = ROOT / "app.py"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def top_imports(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def main() -> int:
    for path in (PERF, ROUTER, STEP2, STEP3, STEP4, APP):
        py_compile.compile(str(path), doraise=True)

    perf = PERF.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    step2 = STEP2.read_text(encoding="utf-8")
    step3 = STEP3.read_text(encoding="utf-8")
    step4 = STEP4.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")

    for heavy in ("pandas", "numpy", "wnba_role_v28", "wnba_api_client_v1", "sports_api"):
        require(heavy not in top_imports(perf), f"Step 5 eagerly imports {heavy}")

    require('"native_on_click_single_rerun": True' in perf, "single-rerun contract missing")
    require("st.rerun()" not in perf, "Step 5 added explicit rerun")
    require('kwargs["on_click"] = callback' in perf, "on_click transport missing")
    require('"speculative_prefetch": False' in perf, "speculative prefetch enabled")
    require('"background_prefetch": False' in perf, "background prefetch enabled")
    require('"prefetch_only_after_explicit_selection": True' in perf, "selection-only prefetch missing")
    require('"prefetch_targets_per_click_max": 1' in perf, "prefetch fanout exceeds one")
    require("SESSION_TTL_SECONDS = 60" in perf, "same-session TTL drift")
    require("duplicate_consumer_read_suppressed=bool(consumer_hit and not history_hit)" in perf, "consumer dedupe telemetry missing")

    for token in (
        '"streamlit_projection_runs_added": 0',
        '"streamlit_sportsbook_calls_added": 0',
        '"streamlit_monte_carlo_runs_added": 0',
        '"projection_math_changed": False',
        '"market_math_changed": False',
        '"sportsbook_projection_influence": 0.0',
    ):
        require(token in perf, f"Step-5 model guardrail missing: {token}")

    require('key=f"wnba_nav_v2_step2_open_{gid}"' in step2, "frozen Slate navigation key drift")
    require('key=f"wnba_nav_v2_step3_player_{game_id}_{pid}"' in step3, "frozen Game navigation key drift")
    require('key="wnba_nav_v2_step3_back_slate"' in step3, "frozen Game back key drift")
    require('key="wnba_nav_v2_step4_back_game"' in step4, "frozen Player back key drift")
    require('"step": "2/7"' in step2 and '"step": "3/7"' in step3 and '"step": "4/7"' in step4, "frozen page contracts drifted")

    require('FROZEN_PLAYER_INTELLIGENCE = "wnba_pra_player_intelligence_v2_step4"' in router, "Step-4 freeze marker missing")
    require('FROZEN_GAME_CENTER = "wnba_pra_game_center_v2_step3"' in router, "Step-3 freeze marker missing")
    require('FROZEN_SLATE = "wnba_pra_slate_v2_step2"' in router, "Step-2 freeze marker missing")
    require('FROZEN_NAVIGATION = "wnba_pra_navigation_v2_step1"' in router, "Step-1 freeze marker missing")
    require("MAY_MODIFY_WNBA_MODEL = False" in router, "model protection missing")
    require("MAY_MODIFY_OTHER_SPORTS = False" in router, "other-sport protection missing")
    require(
        "from streamlit_memory_lazy_router_wnba_nav_v2_step5 import record_bootstrap_import_ms, render_app"
        in app,
        "app does not activate Step-5 router",
    )
    require("Frozen WNBA Navigation V2 Step 4 compatibility" in app, "Step-4 app freeze marker missing")

    print("WNBA_NAV_STEP5_FAST_CERT_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
