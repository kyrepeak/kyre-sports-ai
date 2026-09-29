"""Fast exact-head certification for WNBA Navigation V2 Step 4."""
from __future__ import annotations

import ast
import py_compile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "wnba_pra_player_intelligence_v2_step4.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_nav_v2_step4.py"
STEP3 = ROOT / "wnba_pra_game_center_v2_step3.py"
STEP2 = ROOT / "wnba_pra_slate_v2_step2.py"
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
    for path in (PAGE, ROUTER, STEP3, STEP2, NAV, APP):
        py_compile.compile(str(path), doraise=True)

    page = PAGE.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    step3 = STEP3.read_text(encoding="utf-8")
    step2 = STEP2.read_text(encoding="utf-8")
    nav = NAV.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    imported = top_imports(page)

    require("wnba_api_client_v1" not in imported, "API client eagerly loaded before Player page")
    require("wnba_streamlit_consumer_v2" not in imported, "consumer validator eagerly loaded")
    require("sports_api" not in imported, "backend runtime imported into Streamlit page")
    require("ThreadPoolExecutor(max_workers=2)" in page, "parallel two-read contract missing")
    require("API_TIMEOUT_SECONDS = 5.0" in page, "fast timeout missing")
    require("API_ATTEMPTS = 1" in page, "single attempt missing")
    require("CACHE_TTL_SECONDS = 60" in page, "Player page cache missing")
    require('"network_reads_per_uncached_render_max": 2' in page, "read-count cap missing")

    for token in (
        '"streamlit_projection_runs": 0',
        '"streamlit_sportsbook_calls": 0',
        '"streamlit_qualification_runs": 0',
        '"streamlit_ranking_runs": 0',
        '"streamlit_monte_carlo_runs": 0',
        '"projection_math_changed": False',
        '"market_math_changed": False',
        '"sportsbook_projection_influence": 0.0',
        '"missing_context_fails_closed_to_na": True',
    ):
        require(token in page, f"Step-4 protection missing: {token}")

    for token in (
        "Final Qualified Decision",
        "NO-VIG",
        "EDGE",
        "EV ROI",
        "MC RUNS",
        "Recent Form",
        "Matchup + Pace",
        "Minutes, Role, Usage + Availability",
        "Same-Opponent H2H Context",
        "Advanced diagnostics",
        "NO QUALIFIED PRA CARD",
    ):
        require(token in page, f"Player intelligence surface missing: {token}")

    require('"step": "3/7"' in step3, "frozen Step-3 contract missing")
    require('"step": "2/7"' in step2, "frozen Step-2 contract missing")
    require('"step": "1/7"' in nav, "frozen Step-1 contract missing")
    require('FROZEN_GAME_CENTER = "wnba_pra_game_center_v2_step3"' in router, "Step-3 freeze marker missing")
    require('FROZEN_SLATE = "wnba_pra_slate_v2_step2"' in router, "Step-2 freeze marker missing")
    require('FROZEN_NAVIGATION = "wnba_pra_navigation_v2_step1"' in router, "Step-1 freeze marker missing")
    require('FROZEN_ROUTER = "streamlit_memory_lazy_router_v245"' in router, "V245 delegation missing")
    require("return frozen_renderer(market)" in router, "non-PRA delegation missing")
    require("MAY_MODIFY_WNBA_MODEL = False" in router, "WNBA model protection missing")
    require("MAY_MODIFY_OTHER_SPORTS = False" in router, "other-sport protection missing")
    require(
        "from streamlit_memory_lazy_router_wnba_nav_v2_step4 import record_bootstrap_import_ms, render_app"
        in app,
        "app does not activate Step-4 router",
    )
    require("Frozen WNBA Navigation V2 Step 3 compatibility" in app, "Step-3 app freeze marker missing")

    print("WNBA_NAV_STEP4_FAST_CERT_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
