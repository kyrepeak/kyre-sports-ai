from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "sports_api/collectors/cfb_top_picks_identity_v1.py"
API = ROOT / "sports_api/api/cfb_top_picks_page1_v4.py"
PAGE = ROOT / "cfb_top_picks_page_v15.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v4.py"


def _load(path: Path, name: str):
    if path == API:
        import sports_api as sports_api_pkg
        api_pkg = types.ModuleType("sports_api.api")
        api_pkg.__path__ = [str(ROOT / "sports_api" / "api")]
        api_pkg.__package__ = "sports_api.api"
        sys.modules["sports_api.api"] = api_pkg
        setattr(sports_api_pkg, "api", api_pkg)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v4_files_exist_and_forbidden_provider_paths_are_absent():
    for path in (COLLECTOR, API, PAGE, OVERLAY):
        assert path.exists()
    collector = COLLECTOR.read_text().casefold()
    assert "espn.com" not in collector
    assert "sportsgameodds" not in collector
    assert "sgo" not in collector
    assert "ncaa.com/stats/football/fbs/current/team/742" in collector
    assert "official team athletics roster" in collector


def test_ncaa_index_parser_populates_record_and_logo(monkeypatch):
    identity = _load(COLLECTOR, "cfb_top_picks_identity_v1_test")
    page = '''<table><tr><td>1</td><td><img src="https://www.ncaa.com/logo.svg"><a href="/schools/memphis" class="school">Memphis</a></td><td>5</td><td>2</td><td>0</td><td>.714</td></tr></table>'''
    monkeypatch.setattr(identity, "_get", lambda url: page if not url.endswith(("/p2", "/p3")) else "<table></table>")
    identity.load_ncaa_team_index.cache_clear()
    row = identity.lookup_team("Memphis", identity.load_ncaa_team_index())
    assert row["record"] == "5-2"
    assert row["logo"] == "https://www.ncaa.com/logo.svg"
    assert row["ncaa_school_slug"] == "memphis"


def test_player_alias_is_unique_and_transfer_safe():
    identity = _load(COLLECTOR, "cfb_top_picks_identity_alias_test")
    assert identity._player_alias_match("Ray Joseph Jr.", "Ray Ray Joseph Jr.") is True
    assert identity._player_alias_match("Ray Joseph Jr.", "Ray Smith Jr.") is False


def _payload():
    game = {
        "rank": 1, "event_id": "6603720", "market_type": "MONEYLINE", "selection": "Memphis ML",
        "american_odds": -430, "sportsbook": "FanDuel", "probability": .78,
        "away_team": "East Carolina", "home_team": "Memphis", "away_record": "3-3", "home_record": "5-2",
        "away_logo": "https://www.ncaa.com/ecu.svg", "home_logo": "https://www.ncaa.com/memphis.svg",
        "kickoff_iso": "2026-10-22T23:30:00+00:00",
    }
    prop = {
        "rank": 1, "event_id": "6603720", "player_id": "14335", "player_name": "Emory Williams",
        "player_team": "East Carolina", "player_team_logo": "https://www.ncaa.com/ecu.svg",
        "player_headshot": "https://official.example/emory.jpg", "position": "QB", "jersey_number": "9",
        "opponent": "Memphis", "market_key": "passing_touchdowns", "market_label": "Passing Touchdowns",
        "side": "OVER", "line": .5, "american_odds": -225, "sportsbook": "FanDuel", "probability": .72,
        "away_team": "East Carolina", "home_team": "Memphis", "away_record": "3-3", "home_record": "5-2",
        "away_logo": "https://www.ncaa.com/ecu.svg", "home_logo": "https://www.ncaa.com/memphis.svg",
        "kickoff_iso": "2026-10-22T23:30:00+00:00",
    }
    return {"service": "Kyre Sports API", "selected_date": "2026-10-22", "game_picks": [game], "player_props": [prop]}


def test_v15_page_is_simple_logo_first_and_leak_safe():
    page = _load(PAGE, "cfb_top_picks_page_v15_test")
    html = page._page_html(_payload())
    assert html.startswith("<section")
    assert "\n    <section" not in html
    assert "</section>\n    <section" not in html
    assert "https://www.ncaa.com/ecu.svg" in html
    assert "https://www.ncaa.com/memphis.svg" in html
    assert "Emory Williams" in html and "ID 14335" in html and "#9" in html
    assert "W-L UNAVAILABLE" not in html
    assert "ID not reported" not in html
    assert "WHY THIS PICK" not in html.upper()
    assert "WHY:" not in html.upper()
    assert "Tap for full analysis" in html


def test_v4_wraps_v3_without_changing_ranked_selection(monkeypatch):
    api = _load(API, "cfb_top_picks_page1_v4_test")
    original = _payload()
    monkeypatch.setattr(api.v3, "build_page1_payload", lambda **kwargs: original)
    monkeypatch.setattr(api, "enrich_top_picks_payload", lambda payload: (dict(payload), {"team_identity_matches": 4, "player_identity_matches": 1}))
    out = api.build_page1_payload(game_date="2026-10-22", limit=10)
    assert out["game_picks"] == original["game_picks"]
    assert out["player_props"] == original["player_props"]
    assert out["diagnostics"]["v3_ranking_preserved"] is True
    assert out["routing"]["ranking_math_changed"] is False
    assert out["routing"]["sportsbook_consensus_averaging"] is False
    assert out["routing"]["application_gateway"] == "Kyre Sports API"
