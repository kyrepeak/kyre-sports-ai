from __future__ import annotations

import pandas as pd

import wnba_players_v25 as players


NYL = 1611661313
ATL = 1611661330


def _schedule() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": "1042600202",
                "game_date": "2026-10-07",
                "away_team_id": NYL,
                "away_team": "New York Liberty",
                "away_tricode": "NYL",
                "home_team_id": ATL,
                "home_team": "Atlanta Dream",
                "home_tricode": "ATL",
                "status": "UPCOMING",
            }
        ]
    )


def _production() -> pd.DataFrame:
    base = [
        {
            "PLAYER_ID": 1001,
            "PLAYER_NAME": "Same ID Star",
            "TEAM_ID": NYL,
            "TEAM_NAME": "New York Liberty",
            "TEAM_ABBREVIATION": "NYL",
            "POSITION": "G",
            "GP": 30,
            "MIN": 31.0,
            "PTS": 20.0,
            "REB": 5.0,
            "AST": 6.0,
            "L10_GP": 10,
            "L10_MIN": 32.0,
            "L10_PTS": 21.0,
            "L10_REB": 5.2,
            "L10_AST": 6.4,
            "L5_GP": 5,
            "L5_MIN": 33.0,
            "L5_PTS": 22.0,
            "L5_REB": 5.4,
            "L5_AST": 6.8,
            "DATA_SOURCE": "WNBA Stats",
        },
        {
            "PLAYER_ID": 2002,
            "PLAYER_NAME": "Different ID Star",
            "TEAM_ID": NYL,
            "TEAM_NAME": "New York Liberty",
            "TEAM_ABBREVIATION": "NYL",
            "POSITION": "G",
            "GP": 28,
            "MIN": 29.5,
            "PTS": 18.5,
            "REB": 4.5,
            "AST": 7.0,
            "L10_GP": 10,
            "L10_MIN": 30.0,
            "L10_PTS": 19.0,
            "L10_REB": 4.7,
            "L10_AST": 7.2,
            "L5_GP": 5,
            "L5_MIN": 31.0,
            "L5_PTS": 20.0,
            "L5_REB": 4.8,
            "L5_AST": 7.5,
            "DATA_SOURCE": "WNBA Stats",
        },
        {
            "PLAYER_ID": 4004,
            "PLAYER_NAME": "Waived Historical Player",
            "TEAM_ID": NYL,
            "TEAM_NAME": "New York Liberty",
            "TEAM_ABBREVIATION": "NYL",
            "POSITION": "F",
            "GP": 8,
            "MIN": 12.0,
            "PTS": 4.0,
            "REB": 2.0,
            "AST": 1.0,
            "L10_GP": 8,
            "L10_MIN": 12.0,
            "L10_PTS": 4.0,
            "L10_REB": 2.0,
            "L10_AST": 1.0,
            "L5_GP": 5,
            "L5_MIN": 11.0,
            "L5_PTS": 3.5,
            "L5_REB": 1.8,
            "L5_AST": 0.8,
            "DATA_SOURCE": "WNBA Stats",
        },
        {
            "PLAYER_ID": 3003,
            "PLAYER_NAME": "Atlanta Verified Player",
            "TEAM_ID": ATL,
            "TEAM_NAME": "Atlanta Dream",
            "TEAM_ABBREVIATION": "ATL",
            "POSITION": "F",
            "GP": 31,
            "MIN": 30.0,
            "PTS": 16.0,
            "REB": 8.0,
            "AST": 3.0,
            "L10_GP": 10,
            "L10_MIN": 31.0,
            "L10_PTS": 17.0,
            "L10_REB": 8.2,
            "L10_AST": 3.2,
            "L5_GP": 5,
            "L5_MIN": 32.0,
            "L5_PTS": 18.0,
            "L5_REB": 8.5,
            "L5_AST": 3.5,
            "DATA_SOURCE": "WNBA Stats",
        },
    ]
    return pd.DataFrame(base)


def _ny_roster() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "PLAYER_ID": 1001,
                "PLAYER_NAME": "Same ID Star",
                "TEAM_ID": NYL,
                "TEAM_NAME": "New York Liberty",
                "TEAM_ABBREVIATION": "NYL",
                "POSITION": "G",
                "ROSTER_STATUS": "ACTIVE",
                "PLAYER_ID_SOURCE": "ESPN",
            },
            {
                # ESPN and WNBA Stats identify this same player differently.
                "PLAYER_ID": 999002,
                "PLAYER_NAME": "Different ID Star",
                "TEAM_ID": NYL,
                "TEAM_NAME": "New York Liberty",
                "TEAM_ABBREVIATION": "NYL",
                "POSITION": "G",
                "ROSTER_STATUS": "ACTIVE",
                "PLAYER_ID_SOURCE": "ESPN",
            },
        ]
    )


def test_partial_provider_id_overlap_does_not_delete_name_matched_production(monkeypatch):
    monkeypatch.setattr(players.schedule_v24, "schedule_for_date", lambda _day: _schedule())
    monkeypatch.setattr(players.old_players, "player_form_table", lambda _season: _production())
    monkeypatch.setattr(
        players,
        "_espn_roster",
        lambda team_id, *_args: _ny_roster() if int(team_id) == NYL else pd.DataFrame(),
    )

    players._build_selected_player_pool.clear()
    result, diag = players._build_selected_player_pool("2026-10-07")
    players._build_selected_player_pool.clear()

    names = set(result["PLAYER_NAME"].astype(str))
    assert "Same ID Star" in names
    assert "Different ID Star" in names
    assert "Waived Historical Player" not in names

    mixed_id = result[result["PLAYER_NAME"].eq("Different ID Star")].iloc[0]
    assert int(mixed_id["PLAYER_ID"]) == 2002
    assert float(mixed_id["MIN"]) == 29.5
    assert float(mixed_id["PTS"]) == 18.5
    assert float(mixed_id["REB"]) == 4.5
    assert float(mixed_id["AST"]) == 7.0
    assert float(mixed_id["PRA"]) == 30.0
    assert mixed_id["PLAYER_ID_SOURCE"] == "WNBA Stats"
    assert diag["source"] == "WNBA Stats LeagueID=10"


def test_missing_team_roster_feed_preserves_league_guarded_production(monkeypatch):
    monkeypatch.setattr(players.schedule_v24, "schedule_for_date", lambda _day: _schedule())
    monkeypatch.setattr(players.old_players, "player_form_table", lambda _season: _production())
    monkeypatch.setattr(
        players,
        "_espn_roster",
        lambda team_id, *_args: _ny_roster() if int(team_id) == NYL else pd.DataFrame(),
    )

    players._build_selected_player_pool.clear()
    result, _ = players._build_selected_player_pool("2026-10-07")
    players._build_selected_player_pool.clear()

    atlanta = result[result["PLAYER_NAME"].eq("Atlanta Verified Player")]
    assert len(atlanta) == 1
    row = atlanta.iloc[0]
    assert int(row["PLAYER_ID"]) == 3003
    assert float(row["PTS"]) == 16.0
    assert float(row["REB"]) == 8.0
    assert float(row["AST"]) == 3.0
    assert float(row["PRA"]) == 27.0
