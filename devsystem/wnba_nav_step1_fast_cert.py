"""Fast exact-head certification for WNBA Navigation V2 Step 1.

No network, browser, package install, sportsbook, model, or heavy WNBA imports.
This exists specifically to keep page-building proof cheap and deterministic.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import py_compile
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
NAV = ROOT / "wnba_pra_navigation_v2_step1.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_wnba_nav_v2_step1.py"
APP = ROOT / "app.py"


class FakeQuery(dict):
    pass


class FakeState(dict):
    pass


class FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.query_params = FakeQuery()
        self.session_state = FakeState()


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def import_navigation():
    fake = FakeStreamlit()
    sys.modules["streamlit"] = fake
    spec = importlib.util.spec_from_file_location("wnba_nav_step1_fast_cert_subject", NAV)
    require(spec is not None and spec.loader is not None, "navigation module spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.st = fake
    return module, fake


def main() -> None:
    for path in (NAV, ROUTER, APP):
        py_compile.compile(str(path), doraise=True)

    nav_source = NAV.read_text(encoding="utf-8")
    router_source = ROUTER.read_text(encoding="utf-8")
    app_source = APP.read_text(encoding="utf-8")

    tree = ast.parse(nav_source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    require("pandas" not in imported, "navigation foundation imported pandas")
    require("requests" not in imported, "navigation foundation imported requests")
    require(not any(name.startswith("wnba_") for name in imported), "navigation foundation imported WNBA product module")
    require("market_snapshot(" not in nav_source, "navigation foundation calls market snapshot")

    require('OWNED_SPORT = "WNBA"' in router_source, "router lost WNBA ownership")
    require('OWNED_MARKET = "PRA"' in router_source, "router lost PRA ownership")
    require('FROZEN_ROUTER = "streamlit_memory_lazy_router_v245"' in router_source, "router parent is not frozen V245")
    require("import streamlit_memory_lazy_router_v245 as prior" in router_source, "router does not delegate to V245")
    require("if normalized != OWNED_MARKET:" in router_source, "non-PRA WNBA delegation guard missing")
    require("return frozen_renderer(market)" in router_source, "non-PRA WNBA delegation missing")
    require("navigation.render_step1_foundation" in router_source, "PRA navigation foundation hook missing")
    require("MAY_MODIFY_WNBA_MODEL = False" in router_source, "WNBA model protection missing")
    require("MAY_MODIFY_OTHER_SPORTS = False" in router_source, "other-sport protection missing")
    require("SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in router_source, "sportsbook projection influence changed")

    require(
        "from streamlit_memory_lazy_router_wnba_nav_v2_step1 import record_bootstrap_import_ms, render_app"
        in app_source,
        "app does not activate semantic WNBA Navigation V2 Step 1 router",
    )
    require("Frozen V245 compatibility" in app_source, "V245 compatibility marker missing")

    nav, fake = import_navigation()
    c = nav.NAVIGATION_CONTRACT
    require(c["step"] == "1/7", "wrong Step-1 contract")
    require(c["three_levels"] == ["slate", "game", "player"], "three-page contract missing")
    require(c["default_level"] == "slate", "Slate is not default")
    require(c["heavy_modules_prefetched"] is False, "heavy prefetch enabled")
    require(c["page2_prefetched_from_page1"] is False, "Page 2 prefetch enabled")
    require(c["page3_prefetched_from_page1"] is False, "Page 3 prefetch enabled")
    require(c["page3_prefetched_from_page2"] is False, "Page 3 prefetch from Game enabled")
    require(c["api_ownership_changed"] is False, "API ownership changed")
    require(c["projection_math_changed"] is False, "projection math changed")
    require(c["market_math_changed"] is False, "market math changed")
    require(c["monte_carlo_changed"] is False, "Monte Carlo changed")
    require(c["sportsbook_projection_influence"] == 0.0, "sportsbook influence changed")

    require(nav.normalize_state("garbage") == nav.NavigationState(), "invalid page did not fail closed")
    require(nav.normalize_state("game") == nav.NavigationState(), "game without id did not fail closed")
    require(
        nav.normalize_state("player", "g1") == nav.NavigationState(page="game", game_id="g1"),
        "player without player id did not fall back to game",
    )
    player = nav.NavigationState(page="player", game_id="g1", player_id="p1")
    require(nav.back_state(player) == nav.NavigationState(page="game", game_id="g1"), "player back is wrong")
    require(nav.back_state(nav.NavigationState(page="game", game_id="g1")) == nav.NavigationState(), "game back is wrong")

    nav.go_to_game("g1")
    require(fake.session_state[nav.SESSION_GAME] == "g1", "game session state missing")
    nav.go_to_player("g1", "p1")
    require(nav.current_state() == nav.NavigationState(page="player", game_id="g1", player_id="p1"), "player round trip failed")
    require(nav.go_back() == nav.NavigationState(page="game", game_id="g1"), "go_back player->game failed")
    require(nav.go_to_slate() == nav.NavigationState(), "go_to_slate failed")

    calls = []
    result = nav.render_step1_foundation(lambda: calls.append("legacy") or "ok")
    require(result == "ok" and calls == ["legacy"], "legacy renderer must execute exactly once")
    perf = fake.session_state[nav.PERF_KEY]
    require(perf["future_page_prefetches"] == 0, "future page prefetch detected")
    require(perf["dispatch_ms_before_legacy"] >= 0.0, "dispatch timing missing")

    print("WNBA_NAV_STEP1_FAST_CERT_GREEN")


if __name__ == "__main__":
    main()
