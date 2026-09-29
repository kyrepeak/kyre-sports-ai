"""Fast exact-head certification for WNBA Navigation V2 Step 2."""
from __future__ import annotations

import ast
import py_compile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLATE = ROOT / "wnba_pra_slate_v2_step2.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_nav_v2_step2.py"
NAV = ROOT / "wnba_pra_navigation_v2_step1.py"
APP = ROOT / "app.py"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def imports(source: str) -> set[str]:
    tree = ast.parse(source)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def main() -> int:
    for path in (SLATE, ROUTER, NAV, APP):
        py_compile.compile(str(path), doraise=True)

    slate = SLATE.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    nav = NAV.read_text(encoding="utf-8")
    imported = imports(slate)

    require("pandas" not in imported, "Page 1 imported pandas")
    require("wnba_api_market_bridge_v1" not in imported, "Page 1 imported market bridge")
    require("wnba_players_v25" not in imported, "Page 1 imported player pool")
    require("wnba_context_v26" not in imported, "Page 1 imported context model")
    require("API_TIMEOUT_SECONDS = 5.0" in slate, "fast API timeout missing")
    require("API_ATTEMPTS = 1" in slate, "single API attempt missing")
    require("CACHE_TTL_SECONDS = 60" in slate, "60-second cache missing")
    require("client.games_for_date(day_str, SUPPORTED_SEASON)" in slate, "Kyre schedule call missing")
    require('"schedule_payloads_per_uncached_render": 1' in slate, "one-payload contract missing")

    for token in (
        '"players_loaded": False',
        '"markets_loaded": False',
        '"projections_loaded": False',
        '"rankings_loaded": False',
        '"qualification_loaded": False',
        '"h2h_loaded": False',
        '"monte_carlo_loaded": False',
        '"page2_prefetched": False',
        '"page3_prefetched": False',
        '"sportsbook_projection_influence": 0.0',
    ):
        require(token in slate, f"Step-2 speed protection missing: {token}")

    require('st.date_input("📅 Slate date"' in slate, "Slate date control missing")
    require("cdn.nba.com/logos/wnba/" in slate, "WNBA logos missing")
    require('"Open Game Center →"' in slate, "Game drill-down button missing")
    require("navigation.go_to_game(gid)" in slate, "game state transition missing")
    require("SESSION_SELECTED_GAME" in slate, "selected-game reuse snapshot missing")
    require('"player_requests": 0' in slate, "player prefetch protection missing")
    require('"market_requests": 0' in slate, "market prefetch protection missing")
    require('"model_requests": 0' in slate, "model prefetch protection missing")

    require('OWNED_MARKET = "PRA"' in router, "PRA ownership missing")
    require('FROZEN_NAVIGATION = "wnba_pra_navigation_v2_step1"' in router, "Step-1 freeze missing")
    require('FROZEN_ROUTER = "streamlit_memory_lazy_router_v245"' in router, "V245 delegation missing")
    require("return frozen_renderer(market)" in router, "non-PRA WNBA delegation missing")
    require("return slate.render_step2_route()" in router, "Step-2 route missing")
    require("MAY_MODIFY_WNBA_MODEL = False" in router, "model protection missing")
    require("MAY_MODIFY_OTHER_SPORTS = False" in router, "other-sport protection missing")

    require(
        "from streamlit_memory_lazy_router_wnba_nav_v2_step2 import record_bootstrap_import_ms, render_app"
        in app,
        "app does not activate Step-2 router",
    )
    require("Frozen WNBA Navigation V2 Step 1 compatibility" in app, "Step-1 compatibility marker missing")

    require('"step": "1/7"' in nav, "frozen Step-1 navigation contract missing")
    require('"page2_prefetched_from_page1": False' in nav, "Step-1 no-prefetch contract changed")

    print("WNBA_NAV_STEP2_FAST_CERT_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
