from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_page1_stier_v1.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py"
API_ENTRY = ROOT / "kyre_sports_api_vercel_v1.py"


def test_new_page_exists_and_is_kyre_gateway_only():
    source = PAGE.read_text(encoding="utf-8")
    lower = source.casefold()
    assert 'PAGE1_ENDPOINT = "/api/v1/cfb/game-total/page1"' in source
    assert "Kyre Sports API" in source
    assert "actionnetwork" not in lower
    assert "action network" not in lower
    assert "espn" not in lower
    assert "sportsgameodds" not in lower
    assert "\bsgo\b" not in lower
    assert "cfb_fanduel" not in lower
    assert "the-odds-api.com" not in lower
    assert "api.sportsbook.fanduel.com" not in lower


def test_page_has_professional_game_total_command_center_surfaces():
    source = PAGE.read_text(encoding="utf-8")
    for marker in (
        "Game Totals",
        "MARKET COMMAND CENTER",
        "KYRE SPORTS API",
        "Market Total",
        "Over Price",
        "Under Price",
        "Line Integrity",
        "OPEN ANALYSIS",
    ):
        assert marker in source


def test_terminal_runtime_routes_only_cfb_game_total_to_successor():
    source = TERMINAL.read_text(encoding="utf-8")
    assert 'route.sport_id == "cfb" and route.market_id == "game-total"' in source
    assert 'importlib.import_module("cfb_game_total_page1_stier_v1")' in source
    assert 'importlib.import_module("cfb_game_total_page2_market_completeness_r1")' in source
    assert 'route.sport_id == "nfl" and route.market_id == "passing-yards"' in source
    assert 'route.sport_id == "nba" and route.market_id == "pra"' in source


def test_dedicated_kyre_api_registers_game_total_router():
    source = API_ENTRY.read_text(encoding="utf-8")
    assert "sports_api.api.cfb_game_total_page1_v1" in source
    assert "cfb_game_total_router" in source
    assert "app.include_router(cfb_game_total_router)" in source
