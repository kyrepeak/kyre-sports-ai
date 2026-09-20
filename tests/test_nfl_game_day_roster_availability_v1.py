from __future__ import annotations

from datetime import date

import nfl_game_day_availability_v1 as game_day
import nfl_passing_yards_identity_v1 as identity


def test_unavailable_status_contract() -> None:
    assert game_day.is_unavailable_status("Out")
    assert game_day.is_unavailable_status("Inactive")
    assert game_day.is_unavailable_status("Injured Reserve")
    assert not game_day.is_unavailable_status("Questionable")
    assert not game_day.is_unavailable_status("No listed injury")


def test_event_injury_overrides_league_status() -> None:
    league = {"ATL": [{"athlete_id": "1", "name": "QB One", "status": "No listed injury"}]}
    event = {"ATL": [{"athlete_id": "1", "name": "QB One", "status": "Out"}]}
    merged = game_day.merge_injury_maps(league, event)
    assert merged["ATL"][0]["status"] == "Out"


def test_qb1_falls_through_when_depth_leader_is_out(monkeypatch) -> None:
    monkeypatch.setattr(identity.depth_base, "TEAM_IDS", {"ATL": "1"})
    monkeypatch.setattr(
        identity.depth_base,
        "_depth_payload",
        lambda team_id: (
            {
                "depthCharts": [{
                    "positions": {
                        "qb": {
                            "position": {"abbreviation": "QB"},
                            "athletes": [
                                {"rank": 1, "athlete": {"id": "p", "displayName": "Michael Penix Jr."}},
                                {"rank": 2, "athlete": {"id": "r", "displayName": "Cooper Rush"}},
                            ],
                        }
                    }
                }]
            },
            {"ok": True, "http": 200},
        ),
    )
    result = identity.resolve_team_qb_identity(
        "ATL",
        "Atlanta Falcons",
        2026,
        {
            "ATL": [
                {"athlete_id": "p", "name": "Michael Penix Jr.", "status": "Out", "detail": "Knee"},
                {"athlete_id": "r", "name": "Cooper Rush", "status": "No listed injury", "detail": ""},
            ]
        },
        True,
    )
    assert result["identity_verified"] is True
    assert result["qb1"]["name"] == "Cooper Rush"
    assert result["qb1"]["athlete_id"] == "r"
    assert result["availability_alert"] is True
