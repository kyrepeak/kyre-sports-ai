from __future__ import annotations

from datetime import date
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _game(game_id: str = "g1") -> dict:
    return {
        "game_id": game_id,
        "identity_key": game_id,
        "away_team": "Boise St.",
        "home_team": "Washington St.",
        "away_team_slug": "boise-st",
        "home_team_slug": "washington-st",
        "kickoff_iso": "2026-10-24T22:00:00+00:00",
    }


def test_v8_identity_enrichment_stays_behind_kyre_sports_api():
    page = ROOT / "cfb_moneyline_clean_page_v8.py"
    assert page.exists(), "Moneyline V8 logo-rail successor is missing"
    source = page.read_text(encoding="utf-8")
    assert 'TEAM_IDENTITY_ENDPOINT = "/api/v1/cfb/game-total/page1"' in source
    assert "_api_base() + TEAM_IDENTITY_ENDPOINT" in source
    folded = source.casefold()
    assert "espn" not in folded
    assert "ncaa.com" not in folded


def test_v8_moneyline_horizontal_logo_rail_contract():
    module = importlib.import_module("cfb_moneyline_clean_page_v8")
    games = [_game("g1"), _game("g2")]
    identities = {
        "g1": {
            "away": {"logo_url": "https://assets.invalid/away.svg", "fallback_monogram": "BS"},
            "home": {"logo_url": "https://assets.invalid/home.svg", "fallback_monogram": "WS"},
        },
        "g2": {
            "away": {"logo_url": "", "fallback_monogram": "BS"},
            "home": {"logo_url": "", "fallback_monogram": "WS"},
        },
    }
    html = module._rail_html(games, games[0], date(2026, 10, 24), identities)
    assert "cfbml8-rail" in html
    assert "cfbml8-chip selected" in html
    assert "cfbml8-logo" in html
    assert "BS" in html and "WS" in html
    assert " @ " in html
    assert "3:00 PM" in html
    assert "Phoenix" not in html

    source = (ROOT / "cfb_moneyline_clean_page_v8.py").read_text(encoding="utf-8")
    compact = "".join(source.split()).casefold()
    assert "overflow-x:auto" in compact
    assert "flex-wrap:nowrap" in compact
    assert "scroll-snap-type:xmandatory" in compact
    assert "st.segmented_control(" not in source


def test_moneyline_logo_rail_selection_stays_on_moneyline_page():
    module = importlib.import_module("cfb_moneyline_clean_page_v8")
    href = module._rail_href(_game("g2"), date(2026, 10, 24))
    assert "sport=cfb" in href
    assert "market=moneyline" in href
    assert "cfbml_game=g2" in href
    assert "game_id=" not in href


def test_production_terminal_activates_moneyline_v8_without_model_mutation():
    terminal = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1.py"
    terminal_source = terminal.read_text(encoding="utf-8")
    assert "cfb_moneyline_clean_page_v8" in terminal_source
    assert 'route.sport_id == "cfb" and route.market_id == "moneyline"' in terminal_source
    assert "MAY_MODIFY_PROJECTION = False" in terminal_source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in terminal_source

    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1" in app
