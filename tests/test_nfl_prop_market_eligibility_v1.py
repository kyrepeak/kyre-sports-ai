from __future__ import annotations

from sports_api import nfl_prop_market_eligibility_v1 as gate


def _roster(*players):
    return {
        "athletes": [{
            "position": {"abbreviation": "QB"},
            "displayName": "Quarterbacks",
            "items": [
                {
                    "id": athlete_id,
                    "displayName": name,
                    "position": {"abbreviation": "QB"},
                    "status": "Active",
                    "active": True,
                }
                for athlete_id, name in players
            ],
        }]
    }


def _depth(*players):
    return {
        "depthCharts": [{
            "positions": {
                "qb": {
                    "position": {"abbreviation": "QB"},
                    "athletes": [
                        {"rank": rank, "athlete": {"id": athlete_id, "displayName": name}}
                        for rank, athlete_id, name in players
                    ],
                }
            }
        }]
    }


def _summary(confirmed=True):
    injuries = [
        {
            "team": {"id": "1", "abbreviation": "ATL"},
            "injuries": [{
                "athlete": {"id": "100", "displayName": "Inactive ATL QB"},
                "status": "Inactive",
            }],
        }
    ]
    if confirmed:
        injuries.append({
            "team": {"id": "29", "abbreviation": "CAR"},
            "injuries": [{
                "athlete": {"id": "200", "displayName": "Inactive CAR QB"},
                "status": "Inactive",
            }],
        })
    return {
        "header": {
            "season": {"year": 2026},
            "competitions": [{
                "status": {"type": {"state": "pre", "completed": False}},
                "competitors": [
                    {"team": {"id": "29", "abbreviation": "CAR"}},
                    {"team": {"id": "1", "abbreviation": "ATL"}},
                ],
            }],
        },
        "injuries": injuries,
    }


def _official():
    return {
        "away": {"team_id": "29", "abbr": "CAR"},
        "home": {"team_id": "1", "abbr": "ATL"},
    }


def _espn_get(path, params=None, *, timeout):
    if path == "injuries":
        return {"injuries": []}, "site.api.espn.com"
    if path == "teams/1/depthcharts":
        return _depth(
            (1, "100", "Inactive ATL QB"),
            (2, "101", "Cooper Rush"),
        ), "site.api.espn.com"
    if path == "teams/29/depthcharts":
        return _depth(
            (1, "200", "Inactive CAR QB"),
            (2, "201", "Available CAR QB"),
        ), "site.api.espn.com"
    raise AssertionError(path)


def test_confirmed_event_filters_inactive_depth_players():
    contract = gate.build_event_market_eligibility(
        summary=_summary(True),
        official=_official(),
        roster_payloads_by_team={
            "1": _roster(("100", "Inactive ATL QB"), ("101", "Cooper Rush")),
            "29": _roster(("200", "Inactive CAR QB"), ("201", "Available CAR QB")),
        },
        allowed_positions=frozenset({"QB"}),
        espn_get=_espn_get,
        timeout=1,
    )
    assert contract["availability_state"] == "CONFIRMED"
    assert contract["prop_gate_open"] is True
    assert contract["eligible_ids_by_team"]["1"] == frozenset({"101"})
    assert contract["eligible_ids_by_team"]["29"] == frozenset({"201"})
    assert gate.market_row_eligible(
        {"official_team_id": "1", "official_athlete_id": "101"}, contract
    )
    assert not gate.market_row_eligible(
        {"official_team_id": "1", "official_athlete_id": "100"}, contract
    )


def test_pending_event_leaks_zero_market_players():
    contract = gate.build_event_market_eligibility(
        summary=_summary(False),
        official=_official(),
        roster_payloads_by_team={
            "1": _roster(("100", "Inactive ATL QB"), ("101", "Cooper Rush")),
            "29": _roster(("200", "Inactive CAR QB"), ("201", "Available CAR QB")),
        },
        allowed_positions=frozenset({"QB"}),
        espn_get=_espn_get,
        timeout=1,
    )
    assert contract["availability_state"] == "PENDING"
    assert contract["prop_gate_open"] is False
    assert gate.eligible_player_count(contract) == 0
    assert not gate.market_row_eligible(
        {"official_team_id": "1", "official_athlete_id": "101"}, contract
    )
