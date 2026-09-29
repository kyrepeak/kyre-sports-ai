"""Fast exact-head certification for WNBA Navigation V2 Step 3."""
from __future__ import annotations

import ast
import py_compile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "wnba_pra_game_center_v2_step3.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_nav_v2_step3.py"
SLATE = ROOT / "wnba_pra_slate_v2_step2.py"
NAV = ROOT / "wnba_pra_navigation_v2_step1.py"
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
    for path in (GAME, ROUTER, SLATE, NAV, APP):
        py_compile.compile(str(path), doraise=True)

    game = GAME.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    slate = SLATE.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    imports = top_imports(game)

    for heavy in ("pandas", "numpy", "wnba_role_v28", "wnba_availability_v27"):
        require(heavy not in imports, f"Slate import path eagerly loads {heavy}")

    require("import pandas as pd" in game, "lazy pandas import missing")
    require("import wnba_availability_v27 as availability" in game, "lazy availability import missing")
    require("import wnba_role_v28 as role" in game, "lazy role import missing")
    require("@st.cache_data(ttl=CACHE_TTL_SECONDS" in game, "Game Center cache missing")
    require("CACHE_TTL_SECONDS = 180" in game, "Game Center cache TTL changed")
    require("availability._verified_pool_for_day(str(game_date))" in game, "date-safe player pool missing")
    require("role.role_projection_for_game(selected, stats=stats)" in game, "frozen role batch missing")
    require('"selected_game_projection_batch_calls_per_uncached_render": 1' in game, "one-batch contract missing")

    for token in (
        '"PROJ_MIN"',
        '"PROJ_PTS"',
        '"PROJ_REB"',
        '"PROJ_AST"',
        '"PROJ_PRA"',
        '"STARTER_CONFIRMED"',
        '"ROLE_LABEL"',
        "navigation.go_to_player(game_id, str(pid))",
        "return slate.render_slate_page()",
    ):
        require(token in game, f"Game Center required field/action missing: {token}")

    for token in (
        '"page3_prefetched": False',
        '"sportsbook_markets_loaded": False',
        '"h2h_loaded": False',
        '"ranking_loaded": False',
        '"qualification_loaded": False',
        '"monte_carlo_loaded": False',
        '"projection_math_changed": False',
        '"market_math_changed": False',
        '"sportsbook_projection_influence": 0.0',
    ):
        require(token in game, f"Step-3 protection missing: {token}")

    require('"step": "2/7"' in slate, "frozen Step-2 contract missing")
    require('"step": "1/7"' in NAV.read_text(encoding="utf-8"), "frozen Step-1 contract missing")
    require('FROZEN_SLATE = "wnba_pra_slate_v2_step2"' in router, "Step-2 freeze marker missing")
    require('FROZEN_NAVIGATION = "wnba_pra_navigation_v2_step1"' in router, "Step-1 freeze marker missing")
    require('FROZEN_ROUTER = "streamlit_memory_lazy_router_v245"' in router, "V245 delegation missing")
    require("return frozen_renderer(market)" in router, "non-PRA delegation missing")
    require("MAY_MODIFY_WNBA_MODEL = False" in router, "model protection missing")
    require("MAY_MODIFY_OTHER_SPORTS = False" in router, "other-sport protection missing")
    require(
        "from streamlit_memory_lazy_router_wnba_nav_v2_step3 import record_bootstrap_import_ms, render_app"
        in app,
        "app does not activate Step-3 router",
    )
    require("Frozen WNBA Navigation V2 Step 2 compatibility" in app, "Step-2 app freeze marker missing")

    print("WNBA_NAV_STEP3_FAST_CERT_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
