from __future__ import annotations

import nfl_game_day_availability_v1 as game_day
import nfl_passing_yards_identity_v1 as identity


def test_reserve_practice_squad_and_suspended_rows_are_prop_ineligible() -> None:
    assert not game_day.is_prop_eligible_roster_row({
        "roster_status": "Injured Reserve", "active": False, "group_label": "Tight End"
    })
    assert not game_day.is_prop_eligible_roster_row({
        "roster_status": "", "active": None, "group_label": "Practice Squad"
    })
    assert not game_day.is_prop_eligible_roster_row({
        "roster_status": "Suspended", "active": False, "group_label": "Quarterback"
    })
    assert game_day.is_prop_eligible_roster_row({
        "roster_status": "Active", "active": True, "group_label": "Tight End"
    })
    assert game_day.is_prop_eligible_roster_row({
        "roster_status": "Elevated", "active": True, "group_label": "Practice Squad"
    })


def test_parse_current_roster_carries_transaction_status() -> None:
    payload = {
        "athletes": [{
            "position": "Tight End",
            "items": [
                {
                    "id": "active",
                    "displayName": "Active TE",
                    "position": {"abbreviation": "TE"},
                    "status": {"name": "Active"},
                    "active": True,
                },
                {
                    "id": "ir",
                    "displayName": "IR TE",
                    "position": {"abbreviation": "TE"},
                    "status": {"name": "Injured Reserve"},
                    "active": False,
                },
            ],
        }]
    }
    rows = game_day.parse_current_roster(payload, "SF")
    by_id = {row["athlete_id"]: row for row in rows}
    assert by_id["active"]["prop_eligible"] is True
    assert by_id["ir"]["prop_eligible"] is False


def test_stale_depth_qb_not_on_current_roster_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(identity.depth_base, "TEAM_IDS", {"ATL": "1"})
    monkeypatch.setattr(
        identity.depth_base,
        "_depth_payload",
        lambda _team_id: (
            {
                "depthCharts": [{
                    "positions": {
                        "qb": {
                            "position": {"abbreviation": "QB"},
                            "athletes": [
                                {"rank": 1, "athlete": {"id": "old", "displayName": "Old QB"}},
                                {"rank": 2, "athlete": {"id": "new", "displayName": "Current QB"}},
                            ],
                        }
                    }
                }]
            },
            {"ok": True, "http": 200},
        ),
    )
    monkeypatch.setattr(
        game_day,
        "current_prop_eligible_keys",
        lambda _abbr: ({"new"}, {"current qb"}, {"ok": True, "http": 200}),
    )
    result = identity.resolve_team_qb_identity(
        "ATL", "Atlanta Falcons", 2026, {"ATL": []}, True
    )
    assert result["identity_verified"] is True
    assert result["qb1"]["athlete_id"] == "new"
    assert result["transaction_alert"] is True
