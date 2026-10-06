from __future__ import annotations

import pandas as pd

import wnba_availability_v27 as availability
import wnba_pra_game_center_v2_step3 as game_center
import wnba_pra_player_intelligence_v2_step4 as player_intelligence


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


def test_verified_pool_preserves_canonical_stats_player_id_when_roster_id_differs(monkeypatch):
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

    monkeypatch.setattr(availability.context, "schedule_for_date", lambda _day: _schedule())
    monkeypatch.setattr(availability.players, "player_form_table", lambda _season: raw.copy())
    monkeypatch.setattr(availability, "_rosters_for_schedule", lambda _schedule: roster.copy())

    availability._verified_pool_for_day.clear()
    result, diag = availability._verified_pool_for_day("2026-10-07")
    availability._verified_pool_for_day.clear()

    row = result.iloc[0]
    assert int(row["PLAYER_ID"]) == canonical_wnba_id
    assert row["PLAYER_ID_SOURCE"] == "WNBA Stats"
    assert float(row["PTS"]) == 18.4
    assert diag["state"] == "VERIFIED"


def test_unmatched_roster_id_is_labeled_espn_not_silent_canonical(monkeypatch):
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
    monkeypatch.setattr(availability.context, "schedule_for_date", lambda _day: _schedule())
    monkeypatch.setattr(availability.players, "player_form_table", lambda _season: pd.DataFrame())
    monkeypatch.setattr(availability, "_rosters_for_schedule", lambda _schedule: roster.copy())

    availability._verified_pool_for_day.clear()
    result, _ = availability._verified_pool_for_day("2026-10-07")
    availability._verified_pool_for_day.clear()

    row = result.iloc[0]
    assert int(row["PLAYER_ID"]) == 3149397
    assert row["PLAYER_ID_SOURCE"] == "ESPN"
    assert "no matched production row" in str(row["DATA_SOURCE"])


def test_wnba_id_card_text_never_renders_nan():
    assert game_center._text(float("nan")) == ""
    assert player_intelligence._text(float("nan")) == ""
    assert game_center._text(None) == ""
    assert player_intelligence._text(None) == ""
