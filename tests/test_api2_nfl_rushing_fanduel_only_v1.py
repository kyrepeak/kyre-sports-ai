from __future__ import annotations

import importlib

from universal_runtime_v5_state import RuntimeRoute


def _page():
    return importlib.import_module('nfl_rushing_yards_hub_v18')


def test_fanduel_market_is_hard_display_gate_and_team_order_is_stable() -> None:
    page = _page()
    projections = [
        {'official_athlete_id': 'hou-extra', 'official_team_id': '34', 'expected_carries': 16.0},
        {'official_athlete_id': 'jax-2', 'official_team_id': '30', 'expected_carries': 8.0},
        {'official_athlete_id': 'hou-1', 'official_team_id': '34', 'expected_carries': 14.0},
        {'official_athlete_id': 'jax-1', 'official_team_id': '30', 'expected_carries': 15.0},
    ]
    players = {
        'hou-extra': {'carries_per_game': 12.0},
        'jax-2': {'carries_per_game': 7.0},
        'hou-1': {'carries_per_game': 13.0},
        'jax-1': {'carries_per_game': 14.0},
    }
    markets = {
        'hou-extra': {'ready': False},
        'jax-2': {'ready': True, 'line': 13.5},
        'hou-1': {'ready': True, 'line': 41.5},
        'jax-1': {'ready': True, 'line': 61.5},
    }
    kept = page.select_relevant_rushers(projections, players, markets)
    assert [row['official_athlete_id'] for row in kept] == ['jax-1', 'jax-2', 'hou-1']


def test_market_ready_without_line_is_not_display_eligible() -> None:
    page = _page()
    projections = [
        {'official_athlete_id': '1', 'official_team_id': '30', 'expected_carries': 10.0},
        {'official_athlete_id': '2', 'official_team_id': '30', 'expected_carries': 9.0},
    ]
    players = {'1': {'carries_per_game': 10.0}, '2': {'carries_per_game': 9.0}}
    markets = {'1': {'ready': True, 'line': 61.5}, '2': {'ready': True, 'line': None}}
    kept = page.select_relevant_rushers(projections, players, markets)
    assert [row['official_athlete_id'] for row in kept] == ['1']


def test_v5_overlay_routes_only_nfl_rushing_to_v18() -> None:
    loader = importlib.import_module('universal_runtime_v5_loader_v11')
    rushing = loader.resolve_destination(RuntimeRoute('nfl', 'rushing-yards', {}))
    passing = loader.resolve_destination(RuntimeRoute('nfl', 'passing-yards', {}))
    assert rushing.source_version == 'nfl_rushing_yards_hub_v18'
    assert passing.source_version != 'nfl_rushing_yards_hub_v18'
