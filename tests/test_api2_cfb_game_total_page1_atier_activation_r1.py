from pathlib import Path
import importlib

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "cfb_game_total_page1_api_bootstrap_repair_r1.py"
PAGE = ROOT / "cfb_game_total_page1_atier_v1.py"
APP = ROOT / "app.py"


def _page():
    return importlib.import_module("cfb_game_total_page1_atier_v1")


def test_live_wrapper_delegates_only_page1_to_atier_successor():
    source = WRAPPER.read_text(encoding="utf-8")
    assert "import cfb_game_total_page1_atier_v6 as atier" in source
    assert "return atier.render_game_total_page1()" in source
    assert "prior.render_game_total_page1()" not in source
    assert "https://kyre-sports-api.vercel.app" in source


def test_current_nfl_entrypoint_is_preserved_exactly_as_owner():
    app = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1" in app
    assert "cfb_game_total_page1_atier_v1" not in app


def test_page1_is_kyre_api_only_and_provider_selection_free():
    source = PAGE.read_text(encoding="utf-8")
    lowered = source.casefold()
    assert 'PAGE1_ENDPOINT = "/api/v1/cfb/game-total/page1"' in source
    assert "cfb_game_total_page1_api_bootstrap_repair_r1" in source
    assert "sgo" not in lowered
    assert "espn" not in lowered
    assert "espn bet" not in lowered
    assert "priority =" not in source
    for provider in ("FanDuel", "DraftKings", "BetMGM", "Caesars", "bet365", "Fanatics"):
        assert provider not in source


def test_safe_no_vig_math_and_semantic_empty_states():
    page = _page()
    over, under = page._no_vig_probabilities(-110, -110)
    assert over == pytest.approx(0.5, abs=1e-9)
    assert under == pytest.approx(0.5, abs=1e-9)
    assert page._no_vig_probabilities(None, -110) == (None, None)
    assert page._no_vig_probabilities(0, -110) == (None, None)
    assert page._market_read(None, None, has_total=False)[0] == "MARKET NOT POSTED YET"
    assert page._market_read(None, None, has_total=True)[0] == "PRICE DATA PENDING"
    assert page._market_read(0.50, 0.50, has_total=True)[0] == "BALANCED MARKET"


def test_page1_is_compact_game_total_decision_board():
    source = PAGE.read_text(encoding="utf-8")
    for label in ("MARKET TOTAL", "OVER PRICE", "UNDER PRICE", "NO-VIG MARKET", "MARKET READ", "OPEN ANALYSIS"):
        assert label in source
    for removed in ("Away Spread", "Home Spread", "Moneyline", "cfbgtx-book"):
        assert removed not in source
    assert 'target="_self"' in source
