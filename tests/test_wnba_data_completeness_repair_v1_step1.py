from __future__ import annotations

import pandas as pd

import wnba_availability_v27 as availability


def _schedule() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": "1042600202",
                "game_date": "2026-10-07",
                "away_team_id": 1611661313,
                "home_team_id": 1611661330,
            }
        ]
    )


def _patch_sources(monkeypatch, *, raw: pd.DataFrame, roster: pd.DataFrame) -> None:
    monkeypatch.setattr(availability.context, "schedule_for_date", lambda _day: _schedule())
    monkeypatch.setattr(availability.players, "player_form_table", lambda _season: raw.copy())
    monkeypatch.setattr(availability, "_rosters_for_schedule", lambda _schedule: roster.copy())
    availability._verified_pool_for_day.clear()


def test_verified_pool_preserves_production_player_id_when_roster_id_differs(monkeypatch):
    canonical_wnba_id = 204992
    espn_roster_id = 3149397
    raw = pd.DataFrame(
        [
            {
                "PLAYER_ID": canonical_wnba_id,
                "PLAYER_NAME": "Sabrina Ionescu",
                "TEAM_ID": 1611661313,
                "TEAM_NAME": "New York Liberty",
                "TEAM_ABBREVIATION": "NYL",
                "POSITION": "G",
                "GP": 30,
                "MIN": 31.2,
                "PTS": 18.4,
                "REB": 4.3,
                "AST": 6.1,
                "PRA": 28.8,
                "L10_GP": 10,
                "L10_MIN": 32.0,
                "L10_PTS": 19.0,
                "L10_REB": 4.0,
                "L10_AST": 6.5,
                "L10_PRA": 29.5,
                "L5_GP": 5,
                "L5_MIN": 33.0,
                "L5_PTS": 20.0,
                "L5_REB": 4.2,
                "L5_AST": 6.8,
                "L5_PRA": 31.0,
                "ROSTER_STATUS": "CURRENT TEAM",
                "DATA_SOURCE": "WNBA Stats LeagueID=10",
                "PLAYER_ID_SOURCE": "WNBA Stats",
            }
        ]
    )
    roster = pd.DataFrame(
        [
            {
                "PLAYER_ID": espn_roster_id,
                "PLAYER_NAME": "Sabrina Ionescu",
                "TEAM_ID": 1611661313,
                "TEAM_NAME": "New York Liberty",
                "TEAM_ABBREVIATION": "NYL",
                "POSITION": "G",
                "ROSTER_STATUS": "ACTIVE",
                "PLAYER_ID_SOURCE": "ESPN",
            }
        ]
    )
    _patch_sources(monkeypatch, raw=raw, roster=roster)

    result, diag = availability._verified_pool_for_day("2026-10-07")
    availability._verified_pool_for_day.clear()

    row = result.iloc[0]
    assert int(row["PLAYER_ID"]) == canonical_wnba_id
    assert row["PLAYER_ID_SOURCE"] == "WNBA Stats"
    assert float(row["PTS"]) == 18.4
    assert diag["state"] == "VERIFIED"


def test_unmatched_roster_id_is_explicitly_labeled_espn(monkeypatch):
    roster = pd.DataFrame(
        [
            {
                "PLAYER_ID": 3149397,
                "PLAYER_NAME": "Sabrina Ionescu",
                "TEAM_ID": 1611661313,
                "TEAM_NAME": "New York Liberty",
                "TEAM_ABBREVIATION": "NYL",
                "POSITION": "G",
                "ROSTER_STATUS": "ACTIVE",
                "PLAYER_ID_SOURCE": "ESPN",
            }
        ]
    )
    _patch_sources(monkeypatch, raw=pd.DataFrame(), roster=roster)

    result, _ = availability._verified_pool_for_day("2026-10-07")
    availability._verified_pool_for_day.clear()

    row = result.iloc[0]
    assert int(row["PLAYER_ID"]) == 3149397
    assert row["PLAYER_ID_SOURCE"] == "ESPN"
    assert "no matched production row" in str(row["DATA_SOURCE"])


def test_verified_pool_never_emits_nan_identity_text(monkeypatch):
    raw = pd.DataFrame(
        [
            {
                "PLAYER_ID": 204992,
                "PLAYER_NAME": "Sabrina Ionescu",
                "TEAM_ID": 1611661313,
                "TEAM_NAME": "New York Liberty",
                "TEAM_ABBREVIATION": "NYL",
                "POSITION": float("nan"),
                "GP": 30,
                "MIN": 31.2,
                "PTS": 18.4,
                "REB": 4.3,
                "AST": 6.1,
                "PRA": 28.8,
                "PLAYER_ID_SOURCE": "WNBA Stats",
                "DATA_SOURCE": "WNBA Stats LeagueID=10",
            }
        ]
    )
    roster = pd.DataFrame(
        [
            {
                "PLAYER_ID": 3149397,
                "PLAYER_NAME": "Sabrina Ionescu",
                "TEAM_ID": 1611661313,
                "TEAM_NAME": "New York Liberty",
                "TEAM_ABBREVIATION": "NYL",
                "POSITION": float("nan"),
                "ROSTER_STATUS": "ACTIVE",
                "PLAYER_ID_SOURCE": "ESPN",
            }
        ]
    )
    _patch_sources(monkeypatch, raw=raw, roster=roster)

    result, _ = availability._verified_pool_for_day("2026-10-07")
    availability._verified_pool_for_day.clear()

    row = result.iloc[0]
    assert row["POSITION"] == ""
    assert str(row["POSITION"]).casefold() != "nan"
