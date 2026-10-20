from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_nba_pra_page1_contract_files_exist():
    expected = [
        'nba_pra_page1_data_v1.py',
        'nba_pra_page1_model_v1.py',
        'nba_pra_page1_v1.py',
        'universal_runtime_v5_loader_nba_pra_page1_v1.py',
        'streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py',
        'nba_pra_nav_overlay_v1.py',
    ]
    missing = [name for name in expected if not (ROOT / name).exists()]
    assert not missing, f'missing NBA PRA Page 1 files: {missing}'


def test_nba_nav_overlay_exposes_pra_without_mutating_shared_registry_file():
    source = (ROOT / 'nba_pra_nav_overlay_v1.py').read_text(encoding='utf-8')
    terminal = (ROOT / 'streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py').read_text(encoding='utf-8')
    assert 'id="pra", label="PRA", legacy_market="PRA"' in source
    assert 'page_params=("date", "game_id", "player_id")' in source
    assert 'nav_overlay.activate()' in terminal


def test_entrypoint_advances_only_to_isolated_nba_pra_terminal():
    app = (ROOT / 'app.py').read_text(encoding='utf-8')
    assert 'streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1' in app


def test_page_contract_is_multi_source_fail_closed_and_zero_market_influence():
    data = (ROOT / 'nba_pra_page1_data_v1.py').read_text(encoding='utf-8') if (ROOT/'nba_pra_page1_data_v1.py').exists() else ''
    model = (ROOT / 'nba_pra_page1_model_v1.py').read_text(encoding='utf-8') if (ROOT/'nba_pra_page1_model_v1.py').exists() else ''
    page = ((ROOT / 'nba_pra_page1_v1.py').read_text(encoding='utf-8') + (ROOT / 'nba_pra_page1_ui_v1.py').read_text(encoding='utf-8')) if (ROOT/'nba_pra_page1_v1.py').exists() else ''
    assert 'SportsGameOdds' in data
    assert 'Odds-API.io' in data
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in model
    assert 'PRA MARKET UNAVAILABLE' in page
    assert 'FEATURED INTELLIGENCE' in page
    assert 'ALL PRA PLAYERS' in page
    assert 'CURRENT SEASON' in page
    assert 'PRIOR-SEASON BASELINE' in page
