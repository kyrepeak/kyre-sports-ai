from __future__ import annotations

from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _card(*, verified: bool) -> dict:
    market = {
        "status": "VERIFIED" if verified else "MARKET_NOT_POSTED",
        "sportsbook": "FanDuel" if verified else None,
        "line": 31.5 if verified else None,
        "over_odds": -110 if verified else None,
        "under_odds": -110 if verified else None,
    }
    return {
        "player_id": "kyre:nfl:player:00-0038120",
        "game_id": "kyre:nfl:game:2026_07_PIT_NO",
        "game_date": "2026-10-25",
        "game_time": "2026-10-25T09:30:00-04:00",
        "player_name": "Kendre Miller",
        "role": "RB1",
        "headshot_url": "https://example.com/miller.png",
        "team_abbr": "NO",
        "team_logo_url": "https://example.com/no.svg",
        "opponent_abbr": "PIT",
        "home_away": "HOME",
        "market": market,
        "projection_yards": 33.8,
        "edge_yards": 2.3 if verified else None,
        "favored_side": "OVER" if verified else "CHECK",
        "over_probability": 0.57 if verified else None,
        "under_probability": 0.43 if verified else None,
        "confidence": "LEAN" if verified else "MARKET PENDING",
        "last5_average": 30.6,
        "carries_per_game": 9.8,
        "yards_per_carry": 3.12,
        "opponent_rush_defense_grade": "MEDIUM",
    }


def test_pending_card_is_projection_first_with_one_semantic_pending_state():
    page = import_module("nfl_rushing_yards_simple_rb_grid_v2")
    html = page.build_rb_card_html(_card(verified=False))
    assert html.count('class="kry2projection"') == 1
    assert "KYRE PROJECTION" in html
    assert "33.8" in html and "YDS" in html
    assert html.count('class="kry2decisioncell"') == 3
    assert "MARKET" in html and "EDGE" in html and "MODEL" in html
    assert html.count(">WAIT<") == 0
    assert html.count("Sportsbook line not posted yet • projection ready") == 1
    assert "PENDING" in html
    assert ">0<" not in html and "0.0" not in html
    assert "N/A" not in html and "Unavailable" not in html


def test_verified_card_keeps_real_market_edge_and_model_read():
    page = import_module("nfl_rushing_yards_simple_rb_grid_v2")
    html = page.build_rb_card_html(_card(verified=True))
    assert "FanDuel" in html
    assert "31.5" in html
    assert "+2.3" in html
    assert "OVER" in html
    assert "57%" in html
    assert "LEAN" in html
    assert "Sportsbook line not posted yet" not in html


def test_v2_preserves_quick_stats_team_identity_and_full_analysis_handoff():
    page = import_module("nfl_rushing_yards_simple_rb_grid_v2")
    html = page.build_rb_card_html(_card(verified=False))
    assert "Kendre Miller" in html and "RB1" in html and "HOME vs PIT" in html
    assert "L5 30.6" in html
    assert "9.8 ATT/G" in html
    assert "3.12 YPC" in html
    assert "MEDIUM RUSH D" in html
    assert "FULL ANALYSIS →" in html
    assert "player_id=kyre%3Anfl%3Aplayer%3A00-0038120" in html
    assert "game_id=kyre%3Anfl%3Agame%3A2026_07_PIT_NO" in html
    assert "date=2026-10-25" in html


def test_v2_mobile_css_stays_three_cell_compact_not_two_by_two():
    source = _source("nfl_rushing_yards_simple_rb_grid_v2.py")
    assert ".kry2decision" in source
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in source
    assert "@media(max-width:520px)" in source
    assert "grid-template-columns:repeat(2,1fr)" not in source
    assert ".kry2projection" in source
    assert ".kry2quick" in source
    assert "upcoming games only" in source.lower()


def test_terminal_shadows_only_nfl_rushing_and_app_activates_successor():
    terminal_path = "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_page1_density_r1.py"
    terminal = _source(terminal_path)
    app = _source("app.py")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1" in terminal
    assert 'route.sport_id == "nfl" and route.market_id == "rushing-yards"' in terminal
    assert "nfl_rushing_yards_simple_rb_grid_v2" in terminal
    assert "return _prior_resolve_destination(route)" in terminal
    assert terminal_path.removesuffix(".py") in app
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in terminal
    assert "MAY_MODIFY_PROJECTION = False" in terminal


def test_v2_frontend_contains_no_forbidden_provider_dependency():
    source = _source("nfl_rushing_yards_simple_rb_grid_v2.py") + _source(
        "streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_page1_density_r1.py"
    )
    upper = source.upper()
    for forbidden in ("SGO", "ESPN", "ESPN BET"):
        assert forbidden not in upper
