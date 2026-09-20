from __future__ import annotations

from sports_api import nfl_prop_player_eligibility_v1 as elig


def _summary(state: str = "pre", both_inactive: bool = True):
    injuries = []
    for team_id, athlete_id in (("1", "10"), ("2", "20")):
        status = "Inactive" if both_inactive else ("Inactive" if team_id == "1" else "Questionable")
        injuries.append({
            "team": {"id": team_id},
            "injuries": [{
                "athlete": {"id": athlete_id, "displayName": f"Player {athlete_id}"},
                "status": status,
            }],
        })
    return {
        "header": {
            "competitions": [{
                "status": {"type": {"state": state}},
                "competitors": [
                    {"team": {"id": "1"}},
                    {"team": {"id": "2"}},
                ],
            }]
        },
        "injuries": injuries,
    }


def _roster():
    return {
        "athletes": [
            {
                "position": "Quarterback",
                "items": [
                    {
                        "id": "10",
                        "displayName": "Inactive QB",
                        "position": {"abbreviation": "QB"},
                        "status": {"name": "Active"},
                        "active": True,
                    },
                    {
                        "id": "11",
                        "displayName": "Playable QB",
                        "position": {"abbreviation": "QB"},
                        "status": {"name": "Active"},
                        "active": True,
                    },
                ],
            },
            {
                "position": "injuredReserveOrOut",
                "items": [{
                    "id": "12",
                    "displayName": "IR Runner",
                    "position": {"abbreviation": "RB"},
                    "status": {"name": "Day-To-Day"},
                    "active": None,
                }],
            },
        ]
    }


def _depth():
    return {
        "depthCharts": [{
            "positions": {
                "qb": {
                    "position": {"abbreviation": "QB"},
                    "athletes": [
                        {"rank": 1, "athlete": {"id": "10", "displayName": "Inactive QB"}},
                        {"rank": 2, "athlete": {"id": "11", "displayName": "Playable QB"}},
                    ],
                },
                "rb": {
                    "position": {"abbreviation": "RB"},
                    "athletes": [
                        {"rank": 1, "athlete": {"id": "12", "displayName": "IR Runner"}},
                    ],
                },
            }
        }]
    }


def test_pending_availability_blocks_entire_prop_pool():
    pool, diag = elig.build_current_prop_pool(
        team_id="1",
        roster_payload=_roster(),
        depth_payload=_depth(),
        event_summary=_summary(both_inactive=False),
        allowed_positions={"QB", "RB"},
    )
    assert pool == {}
    assert diag["state"] == "PENDING"
    assert diag["prop_gate_open"] is False


def test_inactive_and_reserve_players_are_removed_but_depth_backup_survives():
    pool, diag = elig.build_current_prop_pool(
        team_id="1",
        roster_payload=_roster(),
        depth_payload=_depth(),
        event_summary=_summary(),
        allowed_positions={"QB", "RB"},
    )
    assert diag["state"] == "CONFIRMED"
    assert "10" not in pool
    assert "12" not in pool
    assert pool["11"]["player_name"] == "Playable QB"
    assert pool["11"]["depth_rank"] == 2


def test_player_not_on_current_depth_chart_cannot_enter_pool():
    roster = _roster()
    roster["athletes"][0]["items"].append({
        "id": "13",
        "displayName": "Roster Only QB",
        "position": {"abbreviation": "QB"},
        "status": {"name": "Active"},
        "active": True,
    })
    pool, _ = elig.build_current_prop_pool(
        team_id="1",
        roster_payload=roster,
        depth_payload=_depth(),
        event_summary=_summary(),
        allowed_positions={"QB", "RB"},
    )
    assert "13" not in pool


def test_live_game_can_confirm_with_out_rows_for_both_teams():
    summary = _summary(state="in", both_inactive=False)
    summary["injuries"][0]["injuries"][0]["status"] = "Out"
    summary["injuries"][1]["injuries"][0]["status"] = "Out"
    state = elig.event_availability_state(summary)
    assert state["state"] == "CONFIRMED"
    assert state["prop_gate_open"] is True


def test_core_depth_shape_extracts_exact_athlete_id_from_ref():
    payload = {
        "items": [{
            "positions": {
                "qb": {
                    "position": {"abbreviation": "QB"},
                    "athletes": [{
                        "rank": 2,
                        "athlete": {
                            "$ref": "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes/12345?lang=en"
                        },
                    }],
                }
            }
        }]
    }
    rows = elig.parse_depth_chart(payload, {"QB"})
    assert rows["12345"]["depth_rank"] == 2
