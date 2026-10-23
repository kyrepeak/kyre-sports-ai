from __future__ import annotations

import time
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


def test_rushing_fastpath_replaces_request_time_pbp_and_bounds_markets():
    fast = import_module("sports_api.nfl_rushing_yards_fastpath_v1")
    assert "stats_player_week_{season}.csv" in fast.PLAYER_STATS_URL
    assert fast.PLAYER_STATS_TIMEOUT_SECONDS <= 6
    assert fast.ROSTER_TIMEOUT_SECONDS <= 6
    assert fast.PREFETCH_BUDGET_SECONDS <= 7.0
    assert fast.MARKET_BUDGET_SECONDS <= 5.0
    assert fast.MARKET_CALL_TIMEOUT_SECONDS <= 3

    legacy = SimpleNamespace(
        _load_pbp=lambda season: None,
        _load_weekly_roster=lambda season: None,
        _completed_rush_rows=lambda frame, cutoff: None,
        _player_game_rows=lambda frame: None,
        _history_rows=lambda season, cutoff, rows: None,
        _collect_markets=lambda games: None,
    )
    fast.install(legacy)
    assert legacy._load_pbp is fast.load_player_stats
    assert legacy._load_weekly_roster is fast.load_weekly_roster
    assert legacy._completed_rush_rows is fast.completed_rush_rows
    assert legacy._player_game_rows is fast.player_game_rows
    assert legacy._history_rows is fast.history_rows
    assert legacy._collect_markets is fast.collect_markets


def test_prewarm_loads_current_roster_and_history_seasons_concurrently(monkeypatch):
    fast = import_module("sports_api.nfl_rushing_yards_fastpath_v1")
    calls: list[tuple[str, int]] = []

    def slow_stats(season: int):
        calls.append(("stats", int(season)))
        time.sleep(0.08)
        return pd.DataFrame()

    def slow_roster(season: int):
        calls.append(("roster", int(season)))
        time.sleep(0.08)
        return pd.DataFrame()

    monkeypatch.setattr(fast, "load_player_stats", slow_stats)
    monkeypatch.setattr(fast, "load_weekly_roster", slow_roster)

    started = time.monotonic()
    state = fast.prewarm_season_inputs(2026, budget_seconds=0.25)
    elapsed = time.monotonic() - started

    assert elapsed < 0.18
    assert set(calls) == {
        ("stats", 2026),
        ("stats", 2025),
        ("stats", 2024),
        ("roster", 2026),
    }
    assert state == {
        "current_stats": True,
        "current_roster": True,
        "history_2025": True,
        "history_2024": True,
    }


def test_weekly_player_stats_preserve_verified_rushing_workload():
    fast = import_module("sports_api.nfl_rushing_yards_fastpath_v1")
    frame = pd.DataFrame([
        {
            "season": 2026,
            "week": 7,
            "season_type": "REG",
            "player_id": "00-TEST",
            "player_display_name": "Lead Back",
            "position": "RB",
            "team": "ATL",
            "opponent_team": "CAR",
            "carries": 18,
            "rushing_yards": 91,
            "rushing_tds": 1,
        }
    ])
    rows = fast.player_game_rows(fast.completed_rush_rows(frame, "2026-10-25"))
    assert rows == [{
        "source_game_id": "2026_07_ATL_CAR",
        "game_date": "",
        "week": 7,
        "team_abbr": "ATL",
        "opponent_abbr": "CAR",
        "player_source_id": "00-TEST",
        "player_name": "Lead Back",
        "attempts": 18,
        "rushing_yards": 91.0,
        "rushing_touchdowns": 1,
    }]


def test_slow_sportsbook_cannot_block_entire_slate(monkeypatch):
    fast = import_module("sports_api.nfl_rushing_yards_fastpath_v1")

    def slow_market(_game, *, timeout=1):
        time.sleep(0.20)
        return [{"sportsbook": "FanDuel"}]

    monkeypatch.setattr(fast.direct_book, "collect_fanduel_game_markets", slow_market)
    games = [{"source_game_id": f"g{i}", "away_name": "A", "home_name": "B"} for i in range(6)]
    started = time.monotonic()
    result = fast.collect_markets(games, budget_seconds=0.02, call_timeout_seconds=1)
    elapsed = time.monotonic() - started

    assert elapsed < 0.15
    assert set(result) == {f"g{i}" for i in range(6)}
    assert all(rows == [] for rows in result.values())


def test_vercel_entrypoint_activates_rushing_fastpath():
    source = (Path(__file__).resolve().parents[1] / "kyre_sports_api_vercel_v1.py").read_text(encoding="utf-8")
    assert "nfl_rushing_yards_fastpath_v1" in source
    assert "nfl_rushing_yards_fastpath.install(nfl_rushing_yards_slate_module)" in source
