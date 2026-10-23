from __future__ import annotations

from datetime import datetime
from importlib import import_module
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_uses_dedicated_rushing_adapter_not_legacy_game_selector():
    source = _source("universal_runtime_v5_loader.py")
    assert "def _nfl_rushing_yards_adapter" in source
    assert 'return _nfl_rushing_yards_adapter(route)' in source
    assert '"rushing-yards": "nfl_rushing_yards_hub_v17"' not in source
    assert "nfl_rushing_yards_simple_rb_grid_v1" in source


def test_page1_is_simple_all_rb_board_without_game_selector():
    source = _source("nfl_rushing_yards_simple_rb_grid_v1.py")
    assert "Running Back Board" in source
    assert "RB1" in source and "RB2" in source
    assert "ks_ry_detail" in source
    assert "View Full Analysis" in source
    assert "selectbox(" not in source
    assert '"🏈 Game"' not in source
    assert "load_rushing_yards_slate" in source


def test_gateway_is_kyre_sports_api_only_and_fail_closed():
    gateway = import_module("nfl_rushing_yards_slate_gateway_v1")
    assert gateway.DEFAULT_API_BASE_URL == "https://kyre-sports-api.vercel.app"
    assert gateway.SCHEMA_VERSION == "nfl_rushing_yards_simple_rb_grid_v1"

    payload = {
        "ready": True,
        "schema_version": gateway.SCHEMA_VERSION,
        "service": "kyre-sports-api",
        "gateway": "Kyre Sports API",
        "running_back_count": 1,
        "running_backs": [
            {
                "player_id": "kyre:nfl:player:00-0031234",
                "game_id": "kyre:nfl:game:2026_08_X_Y",
                "player_name": "Example Runner",
                "team_abbr": "X",
                "opponent_abbr": "Y",
                "game_time": "13:00",
                "role": "RB1",
                "market": {"status": "MARKET_NOT_POSTED", "line": None},
            }
        ],
        "routing": {
            "canonical_ids": True,
            "sportsbook_line_averaging": False,
            "missing_to_zero": False,
            "application_gateway": "Kyre Sports API",
        },
    }
    checked = gateway.validate_payload(payload)
    assert checked["ready"] is True
    assert checked["running_backs"][0]["market"]["line"] is None

    bad = dict(payload)
    bad["running_backs"] = [dict(payload["running_backs"][0], player_id="display-name-only")]
    assert gateway.validate_payload(bad)["ready"] is False


def test_upcoming_filter_removes_started_games_and_rolls_to_next_week():
    slate = import_module("sports_api.api.nfl_rushing_yards_slate_v1")
    now = datetime(2026, 10, 22, 20, 30, tzinfo=ZoneInfo("America/New_York"))
    rows = pd.DataFrame(
        [
            {"season": 2026, "week": 7, "game_type": "REG", "gameday": "2026-10-22", "gametime": "20:15", "away_team": "NE", "home_team": "CHI", "game_id": "g0"},
            {"season": 2026, "week": 7, "game_type": "REG", "gameday": "2026-10-25", "gametime": "13:00", "away_team": "MIA", "home_team": "NYJ", "game_id": "g1"},
            {"season": 2026, "week": 7, "game_type": "REG", "gameday": "2026-10-26", "gametime": "20:15", "away_team": "DAL", "home_team": "PHI", "game_id": "g2"},
            {"season": 2026, "week": 8, "game_type": "REG", "gameday": "2026-10-29", "gametime": "20:15", "away_team": "BUF", "home_team": "KC", "game_id": "g3"},
        ]
    )
    selected = slate.select_upcoming_week(rows, now_et=now)
    assert [row["source_game_id"] for row in selected] == ["g1", "g2"]

    monday_started = datetime(2026, 10, 26, 20, 16, tzinfo=ZoneInfo("America/New_York"))
    rolled = slate.select_upcoming_week(rows, now_et=monday_started)
    assert [row["source_game_id"] for row in rolled] == ["g3"]


def test_rb_selector_returns_only_verified_rb1_and_rb2():
    slate = import_module("sports_api.api.nfl_rushing_yards_slate_v1")
    roster = [
        {"player_source_id": "00-1", "player_name": "Lead Back", "team_abbr": "ATL", "position": "RB", "active": True, "headshot_url": "https://example/a.png"},
        {"player_source_id": "00-2", "player_name": "Second Back", "team_abbr": "ATL", "position": "RB", "active": True, "headshot_url": "https://example/b.png"},
        {"player_source_id": "00-3", "player_name": "Third Back", "team_abbr": "ATL", "position": "RB", "active": True, "headshot_url": "https://example/c.png"},
        {"player_source_id": "00-q", "player_name": "Quarterback", "team_abbr": "ATL", "position": "QB", "active": True},
    ]
    game_rows = [
        {"player_source_id": "00-1", "team_abbr": "ATL", "attempts": 60, "rushing_yards": 310, "games": 5},
        {"player_source_id": "00-2", "team_abbr": "ATL", "attempts": 27, "rushing_yards": 120, "games": 5},
        {"player_source_id": "00-3", "team_abbr": "ATL", "attempts": 4, "rushing_yards": 15, "games": 4},
    ]
    selected = slate.select_team_running_backs("ATL", roster, game_rows)
    assert [row["role"] for row in selected] == ["RB1", "RB2"]
    assert [row["player_source_id"] for row in selected] == ["00-1", "00-2"]
    assert all(row["role_source"] == "VERIFIED_WORKLOAD_DERIVATION" for row in selected)


def test_projection_is_market_blind_and_uses_verified_workload_plus_run_defense():
    model = import_module("nfl_rushing_yards_projection_v2")
    result = model.build_projection(
        player={"carries_per_game": 16.0, "yards_per_carry": 4.5, "sample_games": 5},
        opponent={"yards_per_carry_allowed": 4.0},
    )
    assert result["ready"] is True
    assert round(result["projection_yards"], 1) == 69.2
    assert result["sportsbook_influence"] == 0.0
    assert "market" not in result["inputs"]


def test_semantic_market_state_never_fabricates_zero():
    slate = import_module("sports_api.api.nfl_rushing_yards_slate_v1")
    state = slate.market_state(None)
    assert state == {
        "status": "MARKET_NOT_POSTED",
        "sportsbook": None,
        "market": "Rushing Yards",
        "line": None,
        "over_odds": None,
        "under_odds": None,
        "timestamp": None,
    }


def test_page2_contains_deep_rushing_sections_and_semantic_empty_states():
    page = import_module("nfl_rushing_yards_professional_v1")
    detail = {
        "player_name": "Lead Back",
        "role": "RB1",
        "team_abbr": "ATL",
        "opponent_abbr": "CAR",
        "profile": {"carries_per_game": 16.0, "rushing_yards_per_game": 72.0, "yards_per_carry": 4.5, "recent_games": []},
        "opponent_run_defense": {"rush_yards_allowed_per_game": 130.0, "yards_per_carry_allowed": 4.6, "rank": 27, "grade": "FAVORABLE"},
        "matchup_history": {"status": "FIRST_CAREER_MATCHUP", "games_detail": []},
        "market": {"status": "MARKET_NOT_POSTED", "line": None},
        "availability": {"status": "NO_INJURY_DESIGNATION"},
        "environment": {"status": "PREGAME"},
    }
    html = page.build_rushing_detail_html(detail)
    for label in ("WORKLOAD", "RECENT FORM", "OPPONENT RUN DEFENSE", "MATCHUP HISTORY", "MARKET INTELLIGENCE", "GAME ENVIRONMENT", "AVAILABILITY", "WHY KYRE LEANS"):
        assert label in html
    assert "First career matchup" in html
    assert "Market not posted yet" in html
    assert "Unavailable" not in html
    assert "N/A" not in html


def test_new_production_path_contains_no_banned_provider_dependency():
    production_files = [
        "sports_api/api/nfl_rushing_yards_slate_v1.py",
        "sports_api/collectors/nfl_fanduel_rushing_yards_nflverse_v1.py",
        "nfl_rushing_yards_projection_v2.py",
        "nfl_rushing_yards_slate_gateway_v1.py",
        "nfl_rushing_yards_simple_rb_grid_v1.py",
        "nfl_rushing_yards_professional_v1.py",
    ]
    forbidden = ("SGO", "ESPN", "ESPN BET")
    for path in production_files:
        source = _source(path).upper()
        for token in forbidden:
            assert token not in source, (path, token)


def test_fanduel_collector_excludes_alt_and_combo_markets():
    collector = import_module("sports_api.collectors.nfl_fanduel_rushing_yards_nflverse_v1")
    assert collector.is_standard_rushing_yards_market({"marketType": "PLAYER_X_RUSHING_YARDS", "marketName": "Rushing Yards"})
    assert collector.is_standard_rushing_yards_market({"marketType": "PLAYER_X_RUSHING_YARDS_LOW", "marketName": "Rushing Yards"})
    assert not collector.is_standard_rushing_yards_market({"marketType": "PLAYER_X_RUSHING_YARDS_ALTERNATE", "marketName": "Alt Rushing Yards"})
    assert not collector.is_standard_rushing_yards_market({"marketType": "PLAYER_X_RUSHING_RECEIVING_YARDS", "marketName": "Rushing + Receiving Yards"})


def test_vercel_api_registers_rushing_slate_router():
    source = _source("kyre_sports_api_vercel_v1.py")
    assert "nfl_rushing_yards_slate_module" in source
    assert "app.include_router(nfl_rushing_yards_slate_router)" in source
    assert '"nfl_rushing_yards_slate": True' in source
