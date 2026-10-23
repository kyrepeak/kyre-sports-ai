from pathlib import Path


TERMINAL = Path("streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1.py")
ACTIVE_NBA_PRA_FILES = (
    Path("nba_pra_runtime_v2.py"),
    Path("nba_pra_page1_v2.py"),
    Path("nba_pra_page1_api_only_v1.py"),
    Path("nba_pra_market_api_v1.py"),
    Path("runless_v2/nba_pra_market_v1.py"),
)


def test_terminal_restores_nba_pra_to_api_only_runtime():
    source = TERMINAL.read_text()
    assert 'route.sport_id == "nba" and route.market_id == "pra"' in source
    assert 'importlib.import_module("nba_pra_runtime_v2")' in source
    assert "render_nba_pra_runtime_v2" in source
    assert 'importlib.import_module("nba_pra_page1_v1")' not in source


def test_active_nba_pra_path_has_no_banned_sources_or_direct_legacy_gateway():
    banned = ("SportsGameOdds", "sportsgameodds", "ESPN BET", "ESPN NBA")
    for path in ACTIVE_NBA_PRA_FILES:
        source = path.read_text()
        for token in banned:
            assert token not in source, f"{token!r} leaked into active NBA PRA path via {path}"

    page = Path("nba_pra_page1_v2.py").read_text()
    assert "nba_pra_page1_api_only_v1" in page
    assert "KYRE SPORTS API" in page
