from __future__ import annotations

from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _verified_card() -> dict:
    return {
        "player_id": "kyre:nfl:player:00-0032241",
        "game_id": "kyre:nfl:game:2026_07_ATL_SF",
        "game_date": "2026-10-25",
        "game_time": "2026-10-25T13:00:00-04:00",
        "player_name": "Bijan Robinson",
        "role": "RB1",
        "headshot_url": "https://example.com/bijan.png",
        "team_abbr": "ATL",
        "team_logo_url": "https://example.com/atl.svg",
        "opponent_abbr": "SF",
        "home_away": "HOME",
        "market": {
            "status": "VERIFIED",
            "sportsbook": "FanDuel",
            "line": 87.5,
            "over_odds": -110,
            "under_odds": -110,
        },
        "projection_yards": 92.6,
        "edge_yards": 5.1,
        "favored_side": "OVER",
        "over_probability": 0.55,
        "under_probability": 0.45,
        "confidence": "LEAN",
        "last5_average": 111.6,
        "carries_per_game": 18.5,
        "yards_per_carry": 5.77,
        "opponent_rush_defense_grade": "TOUGH",
    }


def test_all_nfl_team_themes_are_deterministic_and_unknown_falls_back():
    page = import_module("nfl_rushing_yards_simple_rb_grid_v1")
    teams = {
        "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
        "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
        "LV", "LAC", "LAR", "MIA", "MIN", "NE", "NO", "NYG",
        "NYJ", "PHI", "PIT", "SF", "SEA", "TB", "TEN", "WAS",
    }
    assert set(page.TEAM_THEMES) == teams
    for team in teams:
        theme = page.team_theme(team)
        assert set(theme) == {"primary", "secondary", "accent"}
        assert all(value.startswith("#") and len(value) == 7 for value in theme.values())
    assert page.team_theme("UNKNOWN") == {
        "primary": "#0B1B2A",
        "secondary": "#8AD8FF",
        "accent": "#68CDF7",
    }


def test_verified_card_uses_team_identity_and_one_compact_analytics_strip():
    page = import_module("nfl_rushing_yards_simple_rb_grid_v1")
    html = page.build_rb_card_html(_verified_card())
    assert "--team-primary:#A71930" in html
    assert "--team-secondary:#000000" in html
    assert "--team-accent:#A71930" in html
    assert 'class="kry1accent"' in html
    assert html.count('class="kry1analytics"') == 1
    assert 'class="kry1metric"' not in html
    assert html.count('class="kry1scout"') == 1
    assert "ATL" in html and "SF" in html
    assert "MARKET" in html and "KYRE" in html and "EDGE" in html and "MODEL" in html
    assert "+5.1" in html
    assert "kry1positive" in html
    assert "kry1side-positive" in html
    assert "kry1def-tough" in html
    assert "FULL ANALYSIS →" in html
    assert "player_id=kyre%3Anfl%3Aplayer%3A00-0032241" in html
    assert "game_id=kyre%3Anfl%3Agame%3A2026_07_ATL_SF" in html
    assert "date=2026-10-25" in html


def test_market_not_posted_is_intentional_wait_state_without_fake_zero():
    page = import_module("nfl_rushing_yards_simple_rb_grid_v1")
    card = _verified_card()
    card["player_name"] = "Brian Robinson"
    card["role"] = "RB2"
    card["market"] = {
        "status": "MARKET_NOT_POSTED",
        "sportsbook": None,
        "line": None,
        "over_odds": None,
        "under_odds": None,
    }
    card["projection_yards"] = 33.9
    card["edge_yards"] = None
    card["favored_side"] = "CHECK"
    card["over_probability"] = None
    card["under_probability"] = None
    card["confidence"] = "MARKET PENDING"
    html = page.build_rb_card_html(card)
    assert "LINE PENDING" in html
    assert html.count(">WAIT<") >= 2
    assert "Projection ready • sportsbook market not posted" in html
    assert "33.9" in html
    assert ">0<" not in html
    assert "0.0" not in html
    assert "N/A" not in html
    assert "Unavailable" not in html
    assert "kry1pending" in html


def test_page_header_and_css_use_compact_s_tier_contract():
    source = _source("nfl_rushing_yards_simple_rb_grid_v1.py")
    assert "KYRE AI · NFL RUSHING YARDS" in source
    assert "RB Market Board" in source
    assert ".kry1analytics" in source
    assert ".kry1scout" in source
    assert ".kry1accent" in source
    assert ".kry1card *{text-decoration:none!important}" in source
    assert "grid-template-columns:repeat(4,minmax(0,1fr))" in source
    assert "@media(max-width:520px)" in source
    assert "grid-template-columns:repeat(2,1fr)" in source


def test_cleanup_preserves_kyre_gateway_and_frozen_page_architecture():
    source = _source("nfl_rushing_yards_simple_rb_grid_v1.py")
    upper = source.upper()
    assert "load_rushing_yards_slate" in source
    assert "selectbox(" not in source
    assert '"🏈 Game"' not in source
    assert "upcoming games only" in source.lower()
    assert "ks_ry_detail" in source and "ks_ry_game" in source and "ks_ry_date" in source
    assert "Running Back Board" in source  # inherited frozen compatibility marker; not rendered title
    for forbidden in ("SGO", "ESPN", "ESPN BET"):
        assert forbidden not in upper
