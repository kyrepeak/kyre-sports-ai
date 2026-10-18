from __future__ import annotations

from datetime import datetime, timezone
import importlib

import pandas as pd


FIXED_NOW = datetime(2026, 10, 18, 19, 30, tzinfo=timezone.utc)


def _games():
    return pd.DataFrame([
        {"game_id": "final", "state": "post", "date_utc": "2026-10-18T17:00:00Z", "away_team": "A", "home_team": "B"},
        {"game_id": "live", "state": "in", "date_utc": "2026-10-18T18:00:00Z", "away_team": "C", "home_team": "D"},
        {"game_id": "future", "state": "pre", "date_utc": "2026-10-19T00:20:00Z", "away_team": "Dallas Cowboys", "home_team": "Green Bay Packers"},
    ])


def test_future_only_partition_excludes_started_and_final_games():
    mod = importlib.import_module("nfl_universal_future_navigation_v1")
    future = mod.future_only_games(_games(), now_utc=FIXED_NOW)
    assert list(future["game_id"]) == ["future"]


def test_future_only_partition_fails_closed_on_unknown_state():
    mod = importlib.import_module("nfl_universal_future_navigation_v1")
    games = _games().copy()
    games.loc[len(games)] = {"game_id": "mystery", "state": "banana", "date_utc": "2026-10-19T01:00:00Z", "away_team": "X", "home_team": "Y"}
    future = mod.future_only_games(games, now_utc=FIXED_NOW)
    assert "mystery" not in set(future["game_id"])


def test_future_only_partition_requires_future_kickoff_even_when_state_is_pre():
    mod = importlib.import_module("nfl_universal_future_navigation_v1")
    games = pd.DataFrame([
        {"game_id": "stale-pre", "state": "pre", "date_utc": "2026-10-18T19:00:00Z"},
        {"game_id": "future-pre", "state": "pre", "date_utc": "2026-10-18T20:00:00Z"},
    ])
    future = mod.future_only_games(games, now_utc=FIXED_NOW)
    assert list(future["game_id"]) == ["future-pre"]


def test_game_selector_options_remove_started_matchups_without_touching_player_lists():
    mod = importlib.import_module("nfl_universal_future_navigation_v1")
    game_options = [
        "Baltimore Ravens @ Cleveland Browns • 10:00 AM MST",
        "Dallas Cowboys @ Green Bay Packers • 5:20 PM MST",
    ]
    filtered = mod.filter_selector_options(
        "Choose matchup",
        game_options,
        allowed_matchups={"Dallas Cowboys @ Green Bay Packers"},
    )
    assert filtered == ["Dallas Cowboys @ Green Bay Packers • 5:20 PM MST"]
    players = ["Dak Prescott", "Jordan Love"]
    assert mod.filter_selector_options("Player", players, allowed_matchups={"anything"}) == players


def test_loader_v12_installs_tap_only_and_future_filter_for_every_nfl_adapter():
    loader = importlib.import_module("universal_runtime_v5_loader_v12")
    source = open(loader.__file__, "r", encoding="utf-8").read()
    assert "install_universal_tap_only_selectboxes" in source
    assert "install_nfl_future_selector_bridge" in source
    assert "route.sport_id == \"nfl\"" in source


def test_runtime_v5_uses_loader_v12():
    runtime = open("streamlit_memory_lazy_router_universal_runtime_v5.py", "r", encoding="utf-8").read()
    assert "from universal_runtime_v5_loader_v12 import" in runtime


def test_future_navigation_declares_no_model_mutation():
    mod = importlib.import_module("nfl_universal_future_navigation_v1")
    assert mod.MAY_MODIFY_PROJECTION is False
    assert mod.MAY_MODIFY_PROBABILITY is False
    assert mod.MAY_MODIFY_MARKET_MATH is False
    assert mod.STAKE_SIZING_ENABLED is False
