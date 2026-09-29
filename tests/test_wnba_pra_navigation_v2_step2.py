from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLATE = (ROOT / "wnba_pra_slate_v2_step2.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "streamlit_memory_lazy_router_wnba_nav_v2_step2.py").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def _imports(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_step2_is_schedule_only_and_uses_fast_api_contract():
    imports = _imports(SLATE)
    assert "pandas" not in imports
    assert "wnba_api_market_bridge_v1" not in imports
    assert "wnba_players_v25" not in imports
    assert "wnba_context_v26" not in imports
    assert "KyreWNBAAPIClient(" in SLATE
    assert "timeout_seconds=API_TIMEOUT_SECONDS" in SLATE
    assert "attempts=API_ATTEMPTS" in SLATE
    assert "API_TIMEOUT_SECONDS = 5.0" in SLATE
    assert "API_ATTEMPTS = 1" in SLATE
    assert "@st.cache_data(ttl=CACHE_TTL_SECONDS" in SLATE
    assert "CACHE_TTL_SECONDS = 60" in SLATE
    assert "client.games_for_date(day_str, SUPPORTED_SEASON)" in SLATE


def test_step2_contract_forbids_heavy_page1_work():
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
        assert token in SLATE


def test_step2_slate_contains_required_user_surface_and_navigation():
    assert 'st.date_input("📅 Slate date"' in SLATE
    assert "cdn.nba.com/logos/wnba/" in SLATE
    assert '"time_label"' in SLATE
    assert '"status_text"' in SLATE
    assert '"Open Game Center →"' in SLATE
    assert "navigation.go_to_game(gid)" in SLATE
    assert "SESSION_SELECTED_GAME" in SLATE
    assert '"schedule_requests_this_render": 1' in SLATE
    assert '"player_requests": 0' in SLATE
    assert '"market_requests": 0' in SLATE
    assert '"model_requests": 0' in SLATE


def test_step2_deeper_placeholder_does_not_load_schedule():
    tree = ast.parse(SLATE)
    target = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_render_deeper_placeholder"
    )
    body = ast.get_source_segment(SLATE, target) or ""
    assert "load_slate(" not in body
    assert "navigation.go_to_slate()" in body


def test_step2_router_owns_only_wnba_pra():
    assert 'OWNED_SPORT = "WNBA"' in ROUTER
    assert 'OWNED_MARKET = "PRA"' in ROUTER
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v245"' in ROUTER
    assert 'FROZEN_NAVIGATION = "wnba_pra_navigation_v2_step1"' in ROUTER
    assert "if normalized != OWNED_MARKET:" in ROUTER
    assert "return frozen_renderer(market)" in ROUTER
    assert "return slate.render_step2_route()" in ROUTER
    assert "MAY_MODIFY_WNBA_MODEL = False" in ROUTER
    assert "MAY_MODIFY_OTHER_SPORTS = False" in ROUTER
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in ROUTER


def test_app_activates_step2_and_keeps_step1_freeze_marker():
    assert "from streamlit_memory_lazy_router_wnba_nav_v2_step2 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen WNBA Navigation V2 Step 1 compatibility" in APP
