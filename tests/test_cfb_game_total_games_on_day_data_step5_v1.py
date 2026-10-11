from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V42 = ROOT / "cfb_game_total_clean_page_v42.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
V41 = ROOT / "cfb_game_total_clean_page_v41.py"


def test_step5_requires_one_authoritative_selected_day_snapshot():
    assert V42.exists(), "Step 5 must add V42 as the games-on-day data owner"
    source = V42.read_text()

    assert "import cfb_game_total_clean_page_v41 as prior" in source
    assert "import cfb_game_total_clean_page_v14 as games_owner" in source
    assert 'GAMES_ON_DAY_DATA_MARKER = "CFB_GAME_TOTAL_GAMES_ON_DAY_DATA_STEP5_ACTIVE"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "NETWORK_CALLS_ADDED = 0" in source
    assert "NEW_PROVIDER_PATHS_ADDED = 0" in source
    assert "SELECTED_DAY_SNAPSHOT_OWNS_GAME_LOADING = True" in source

    assert "selected_day = prior._selected_day()" in source
    assert "original_loader = games_owner._load_games" in source
    assert "snapshot = tuple(dict(game) for game in original_loader(selected_day))" in source
    assert "def snapshot_loader(requested_day):" in source
    assert "if requested_day != selected_day:" in source
    assert "games_owner._load_games = snapshot_loader" in source
    assert "games_owner._load_games = original_loader" in source

    assert "requests." not in source
    assert "load_with_diagnostics(" not in source


def test_step5_advances_only_page1_owner_and_keeps_step4_frozen():
    router = ROUTER.read_text()
    v41 = V41.read_text()

    assert 'PAGE1_NATIVE_ROUTE = "cfb_game_total_clean_page_v42"' in router
    assert 'PAGE2_RUNTIME = "cfb_game_total_page2_step8_final_runtime_v1"' in router
    assert "SELECTOR_OWNS_GAME_LOADING = False" in v41
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v41"' in V42.read_text()
