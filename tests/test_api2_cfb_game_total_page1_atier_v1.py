from pathlib import Path
import importlib

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_page1_atier_v1.py"
LOADER = ROOT / "universal_runtime_v5_loader_cfb_game_total_page1_atier_v1.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_cfb_game_total_page1_atier_v1.py"
APP = ROOT / "app.py"


def _page():
    assert PAGE.exists(), "A-tier Page 1 successor has not been implemented yet"
    return importlib.import_module("cfb_game_total_page1_atier_v1")


def test_page1_successor_exists_and_is_kyre_api_only():
    assert PAGE.exists(), "A-tier Page 1 successor has not been implemented yet"
    src = PAGE.read_text(encoding="utf-8")
    assert 'PAGE1_ENDPOINT = "/api/v1/cfb/game-total/page1"' in src
    assert "cfb_game_total_page1_api_bootstrap_repair_r1" in src
    lowered = src.casefold()
    assert "sgo" not in lowered
    assert "espn" not in lowered
    assert "espn bet" not in lowered
    assert "sports_api.collectors" not in src
    assert "requests.get(" not in src


def test_no_vig_market_probability_is_safe_and_deterministic():
    page = _page()
    over, under = page._no_vig_probabilities(-110, -110)
    assert over == pytest.approx(0.5, abs=1e-9)
    assert under == pytest.approx(0.5, abs=1e-9)

    over, under = page._no_vig_probabilities(-120, 100)
    assert over is not None and under is not None
    assert over > under
    assert over + under == pytest.approx(1.0, abs=1e-9)

    assert page._no_vig_probabilities(None, -110) == (None, None)
    assert page._no_vig_probabilities("", -110) == (None, None)
    assert page._no_vig_probabilities(0, -110) == (None, None)


def test_market_read_never_fabricates_missing_data():
    page = _page()
    assert page._market_read(None, None, has_total=False) == (
        "MARKET NOT POSTED YET",
        "No verified game-total quote is currently available through Kyre Sports API.",
        "empty",
    )
    assert page._market_read(None, None, has_total=True)[0] == "PRICE DATA PENDING"
    assert page._market_read(0.50, 0.50, has_total=True)[0] == "BALANCED MARKET"
    assert page._market_read(0.54, 0.46, has_total=True)[0] == "OVER MARKET LEAN"
    assert page._market_read(0.46, 0.54, has_total=True)[0] == "UNDER MARKET LEAN"


def test_page1_card_is_compact_game_total_only():
    assert PAGE.exists(), "A-tier Page 1 successor has not been implemented yet"
    src = PAGE.read_text(encoding="utf-8")
    for label in (
        "MARKET TOTAL",
        "OVER PRICE",
        "UNDER PRICE",
        "NO-VIG MARKET",
        "MARKET READ",
        "OPEN ANALYSIS",
    ):
        assert label in src
    assert "Away Spread" not in src
    assert "Home Spread" not in src
    assert "Moneyline" not in src
    assert "cfbgtx-book" not in src
    assert 'target="_self"' in src


def test_loader_replaces_only_page1_owner_and_preserves_page2():
    assert LOADER.exists(), "A-tier runtime loader has not been implemented yet"
    src = LOADER.read_text(encoding="utf-8")
    assert 'importlib.import_module("cfb_game_total_page1_atier_v1")' in src
    assert 'importlib.import_module("cfb_game_total_page2_market_completeness_r1")' in src
    assert 'route.sport_id == "cfb" and route.market_id == "game-total"' in src


def test_terminal_and_app_activate_atier_successor():
    assert TERMINAL.exists(), "A-tier terminal has not been implemented yet"
    terminal = TERMINAL.read_text(encoding="utf-8")
    assert "universal_runtime_v5_loader_cfb_game_total_page1_atier_v1" in terminal
    app = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_game_total_page1_atier_v1" in app
