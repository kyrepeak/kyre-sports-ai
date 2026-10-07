from __future__ import annotations

import pandas as pd

import wnba_availability_v27 as availability


def _schedule():
    return pd.DataFrame(
        [
            {
                "away_team_id": 100,
                "home_team_id": 200,
            }
        ]
    )


def _roster():
    return pd.DataFrame(
        [
            {
                "PLAYER_ID": 1,
                "PLAYER_NAME": "Test Player",
                "TEAM_ID": 100,
                "TEAM_NAME": "Away",
                "TEAM_ABBREVIATION": "AWY",
                "POSITION": "G",
                "ROSTER_STATUS": "ACTIVE",
                "PLAYER_ID_SOURCE": "ESPN",
            }
        ]
    )


def _hydrated_player_pool():
    row = {column: pd.NA for column in availability.players.PLAYER_COLUMNS}
    row.update(
        {
            "PLAYER_ID": 1,
            "PLAYER_NAME": "Test Player",
            "TEAM_ID": 100,
            "TEAM_NAME": "Away",
            "TEAM_ABBREVIATION": "AWY",
            "POSITION": "G",
            "ROSTER_STATUS": "ACTIVE",
            "PLAYER_ID_SOURCE": "ESPN",
            "GP": 20,
            "MIN": 31.5,
            "PTS": 17.25,
            "REB": 5.5,
            "AST": 4.25,
            "PRA": 27.0,
            "L10_GP": 10,
            "L10_MIN": 32.0,
            "L10_PTS": 18.0,
            "L10_REB": 6.0,
            "L10_AST": 4.0,
            "L10_PRA": 28.0,
            "L5_GP": 5,
            "L5_MIN": 33.0,
            "L5_PTS": 19.0,
            "L5_REB": 6.0,
            "L5_AST": 5.0,
            "L5_PRA": 30.0,
            "DATA_SOURCE": "ESPN WNBA Athlete Gamelog",
        }
    )
    return pd.DataFrame([row], columns=availability.players.PLAYER_COLUMNS)


def test_verified_pool_hydrates_the_exact_requested_day(monkeypatch):
    requested = []

    monkeypatch.setattr(availability.context, "schedule_for_date", lambda day: _schedule())
    monkeypatch.setattr(availability, "_rosters_for_schedule", lambda schedule: _roster())

    def exact_day_builder(day):
        requested.append(str(day))
        return _hydrated_player_pool(), {"state": "VERIFIED"}

    monkeypatch.setattr(availability.players, "_build_selected_player_pool", exact_day_builder)

    def wrong_owner(_season):
        raise AssertionError("selected-day handoff must not use player_form_table(year)")

    monkeypatch.setattr(availability.players, "player_form_table", wrong_owner)

    availability._verified_pool_for_day.clear()
    pool, diag = availability._verified_pool_for_day("2026-10-07")

    assert requested == ["2026-10-07"]
    assert diag["state"] == "VERIFIED"
    assert len(pool) == 1
    assert float(pool.iloc[0]["PTS"]) == 17.25
    assert float(pool.iloc[0]["REB"]) == 5.5
    assert float(pool.iloc[0]["AST"]) == 4.25
    assert float(pool.iloc[0]["PRA"]) == 27.0
    assert pool.iloc[0]["DATA_SOURCE"] == "ESPN WNBA Athlete Gamelog"
