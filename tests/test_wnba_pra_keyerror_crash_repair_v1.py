from __future__ import annotations

import pandas as pd

import wnba_role_v282 as role


def _game_row() -> pd.Series:
    return pd.Series({
        "game_id": "401999001",
        "game_date": "2026-10-19",
        "away_team_id": 1,
        "home_team_id": 2,
        "away_team": "Atlanta Dream",
        "home_team": "Golden State Valkyries",
    })


def test_role_projection_empty_player_pool_fails_closed_instead_of_keyerror(monkeypatch):
    monkeypatch.setattr(role.base.availability, "availability_for_game", lambda row, stats: {"players": pd.DataFrame(), "source": "test"})
    monkeypatch.setattr(role.base.availability, "slate_player_pool", lambda schedule, stats: pd.DataFrame())
    monkeypatch.setattr(role, "advanced_usage_table", lambda season: (pd.DataFrame(), "unavailable"))
    role.base.advanced_usage_table = role.advanced_usage_table

    result = role.role_projection_for_game(_game_row(), pd.DataFrame())

    assert set(result["teams"]) == {1, 2}
    assert result["teams"][1].empty
    assert result["teams"][2].empty
    assert result["usage_source"] == "unavailable"
