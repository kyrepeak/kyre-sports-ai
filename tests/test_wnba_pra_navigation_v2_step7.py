from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEP7 = (ROOT / "wnba_pra_final_v2_step7.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "streamlit_memory_lazy_router_wnba_nav_v2_step7.py").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_step7_navigation_commits_state_before_destination_work():
    game_fn = STEP7.split("def _open_game_immediate", 1)[1].split("def _open_player_immediate", 1)[0]
    player_fn = STEP7.split("def _open_player_immediate", 1)[1].split("def _step7_button_callback", 1)[0]

    assert "navigation.go_to_game(game_id)" in game_fn
    assert "navigation.go_to_player(str(game_id), str(player_id))" in player_fn
    assert "_prefetch_game(" not in game_fn
    assert "_prefetch_player(" not in player_fn
    assert 'prefetch_status="deferred_until_destination"' in game_fn
    assert 'prefetch_status="deferred_until_destination"' in player_fn


def test_step7_preserves_frozen_step6_responsive_layer():
    assert "import wnba_pra_responsive_v2_step6 as responsive" in STEP7
    assert "return responsive.render_step6_route()" in STEP7
    assert '"frozen_steps_1_through_6_modified": False' in STEP7
    assert '"projection_math_changed": False' in STEP7
    assert '"market_math_changed": False' in STEP7
    assert '"sportsbook_projection_influence": 0.0' in STEP7


def test_step7_marker_and_router_activation():
    assert 'data-wnba-nav-v2-step7="final-transport"' in STEP7
    assert 'FROZEN_RESPONSIVE = "wnba_pra_responsive_v2_step6"' in ROUTER
    assert 'FROZEN_STEP6_ROUTER = "streamlit_memory_lazy_router_wnba_nav_v2_step6"' in ROUTER
    assert "return final.render_step7_route()" in ROUTER
    assert "MAY_MODIFY_WNBA_MODEL = False" in ROUTER
    assert "MAY_MODIFY_OTHER_SPORTS = False" in ROUTER
    assert "from streamlit_memory_lazy_router_wnba_nav_v2_step7 import record_bootstrap_import_ms, render_app" in APP
