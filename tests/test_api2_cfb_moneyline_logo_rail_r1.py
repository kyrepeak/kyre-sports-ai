from __future__ import annotations

from datetime import date
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = importlib.import_module("sports_api.api.cfb_moneyline_page1_v1")


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


def test_moneyline_api_owns_team_identity_assets():
    row = API._public_game(_game(), [])
    assert row["team_identity"]["away"]["kyre_team_id"] == "KYRE-CFB-boise-st"
    assert row["team_identity"]["home"]["kyre_team_id"] == "KYRE-CFB-washington-st"
    assert row["team_identity"]["away"]["logo_url"].endswith("/boise-st.svg")
    assert row["team_identity"]["home"]["logo_url"].endswith("/washington-st.svg")


def test_v8_moneyline_horizontal_logo_rail_contract():
    page = ROOT / "cfb_moneyline_clean_page_v8.py"
    assert page.exists(), "Moneyline V8 logo-rail successor is missing"
    module = importlib.import_module("cfb_moneyline_clean_page_v8")
    games = [_game("g1"), _game("g2")]
    for game in games:
        game["team_identity"] = {
            "away": {"logo_url": "https://assets.invalid/away.svg", "fallback_monogram": "BS"},
            "home": {"logo_url": "https://assets.invalid/home.svg", "fallback_monogram": "WS"},
        }
    selected = games[0]
    html = module._rail_html(games, selected, date(2026, 10, 24))
    assert "cfbml8-rail" in html
    assert "cfbml8-chip selected" in html
    assert "cfbml8-logo" in html
    assert "BS" in html and "WS" in html
    assert " @ " in html
    assert "3:00 PM" in html
    assert "Phoenix" not in html

    source = page.read_text(encoding="utf-8")
    compact = "".join(source.split()).casefold()
    assert "overflow-x:auto" in compact
    assert "flex-wrap:nowrap" in compact
    assert "scroll-snap-type:xmandatory" in compact
    assert "st.segmented_control" not in source


def test_moneyline_logo_rail_selection_stays_on_moneyline_page():
    module = importlib.import_module("cfb_moneyline_clean_page_v8")
    href = module._rail_href(_game("g2"), date(2026, 10, 24))
    assert "sport=cfb" in href
    assert "market=moneyline" in href
    assert "cfbml_game=g2" in href
    assert "game_id=" not in href


def test_production_terminal_activates_moneyline_v8_without_model_mutation():
    terminal = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_cfb_moneyline_logo_rail_r1.py"
    assert terminal.exists(), "Moneyline logo-rail production terminal is missing"
    terminal_source = terminal.read_text(encoding="utf-8")
    assert "cfb_moneyline_clean_page_v8" in terminal_source
    assert "MAY_MODIFY_PROJECTION = False" in terminal_source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in terminal_source

    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_moneyline_logo_rail_r1" in app
