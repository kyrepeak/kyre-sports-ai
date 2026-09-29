from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME = (ROOT / "wnba_pra_game_center_v2_step3.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "streamlit_memory_lazy_router_wnba_nav_v2_step3.py").read_text(encoding="utf-8")
SLATE = (ROOT / "wnba_pra_slate_v2_step2.py").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def _top_level_imports(source: str) -> set[str]:
    tree = ast.parse(source)
    result: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_step3_keeps_heavy_role_engine_off_slate_import_path():
    top = _top_level_imports(GAME)
    assert "pandas" not in top
    assert "numpy" not in top
    assert "wnba_role_v28" not in top
    assert "wnba_availability_v27" not in top
    assert "import pandas as pd" in GAME
    assert "import wnba_availability_v27 as availability" in GAME
    assert "import wnba_role_v28 as role" in GAME


def test_step3_uses_one_cached_selected_game_batch():
    assert "@st.cache_data(ttl=CACHE_TTL_SECONDS" in GAME
    assert "CACHE_TTL_SECONDS = 180" in GAME
    assert "availability._verified_pool_for_day(str(game_date))" in GAME
    assert "role.role_projection_for_game(selected, stats=stats)" in GAME
    assert '"selected_game_projection_batch_calls_per_uncached_render": 1' in GAME
    assert '"selected_game_output_only": True' in GAME


def test_step3_player_cards_show_required_projection_fields():
    for token in (
        '"STARTER_CONFIRMED"',
        '"ROLE_LABEL"',
        '"PROJ_MIN"',
        '"PROJ_PTS"',
        '"PROJ_REB"',
        '"PROJ_AST"',
        '"PROJ_PRA"',
        '"MIN"',
        '"PTS"',
        '"REB"',
        '"AST"',
        '"PRA"',
    ):
        assert token in GAME
    assert "cdn.wnba.com/headshots/wnba/latest/1040x760/" in GAME
    assert "cdn.nba.com/logos/wnba/" in GAME


def test_step3_player_tap_writes_frozen_navigation_state():
    assert "SESSION_SELECTED_PLAYER" in GAME
    assert "navigation.go_to_player(game_id, str(pid))" in GAME
    assert "navigation.go_to_game(state.game_id)" in GAME
    assert "navigation.go_to_slate()" in GAME


def test_step3_does_not_prefetch_page3_or_market_mc_layers():
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
        assert token in GAME
    assert '"page3_prefetches": 0' in GAME
    assert '"sportsbook_market_requests": 0' in GAME
    assert '"h2h_requests": 0' in GAME
    assert '"monte_carlo_requests": 0' in GAME


def test_step3_reuses_frozen_step2_slate_without_editing_its_contract():
    assert "return slate.render_slate_page()" in GAME
    assert '"step": "2/7"' in SLATE
    assert '"page2_prefetched": False' in SLATE
    assert '"page3_prefetched": False' in SLATE


def test_step3_router_owns_only_wnba_pra_and_freezes_prior_layers():
    assert 'OWNED_SPORT = "WNBA"' in ROUTER
    assert 'OWNED_MARKET = "PRA"' in ROUTER
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v245"' in ROUTER
    assert 'FROZEN_NAVIGATION = "wnba_pra_navigation_v2_step1"' in ROUTER
    assert 'FROZEN_SLATE = "wnba_pra_slate_v2_step2"' in ROUTER
    assert "if normalized != OWNED_MARKET:" in ROUTER
    assert "return frozen_renderer(market)" in ROUTER
    assert "return game_center.render_step3_route()" in ROUTER
    assert "MAY_MODIFY_WNBA_MODEL = False" in ROUTER
    assert "MAY_MODIFY_OTHER_SPORTS = False" in ROUTER


def test_app_activates_step3_and_preserves_step2_freeze_marker():
    assert "from streamlit_memory_lazy_router_wnba_nav_v2_step3 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen WNBA Navigation V2 Step 2 compatibility" in APP
