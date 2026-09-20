import pytest

from nfl_prop_app_eligibility_v1 import guard_passing_identity


def _resolved():
    return {
        "ready": False,
        "identity_ready": True,
        "prop_availability_ready": False,
        "availability_state": "PENDING",
        "game_id": "401999999",
        "reason": "final game-day inactive confirmation is still pending",
        "away": {
            "team_id": "1",
            "abbr": "ATL",
            "identity_verified": True,
            "qbs": [{"athlete_id": "101", "name": "Away QB"}],
            "qb1": {"athlete_id": "101", "name": "Away QB"},
        },
        "home": {
            "team_id": "2",
            "abbr": "CAR",
            "identity_verified": True,
            "qbs": [{"athlete_id": "202", "name": "Home QB"}],
            "qb1": {"athlete_id": "202", "name": "Home QB"},
        },
    }


@pytest.mark.parametrize("state", ["PENDING", "CLOSED"])
def test_verified_qb_identity_survives_closed_prop_gate(state):
    resolved = _resolved()
    snapshot = {
        "ready": True,
        "state": state,
        "prop_gate_open": False,
        "reason": "pregame prop identity closed or pending",
        "team_by_id": {"1": "ATL", "2": "CAR"},
    }

    roster = {
        "ATL": ({"101"}, {"ok": True}),
        "CAR": ({"202"}, {"ok": True}),
    }

    out = guard_passing_identity(
        {"game_id": "401999999"},
        resolved,
        snapshot_loader=lambda event_id: snapshot,
        roster_loader=lambda abbr: roster[abbr],
    )

    assert out["ready"] is False
    assert out["prop_availability_ready"] is False
    assert out["step7_app_identity_verified"] is True
    assert out["step7_app_identity_state"] == state
    assert out["away"]["identity_verified"] is True
    assert out["away"]["qb1"]["athlete_id"] == "101"
    assert out["away"]["qb1"]["name"] == "Away QB"
    assert out["home"]["identity_verified"] is True
    assert out["home"]["qb1"]["athlete_id"] == "202"
    assert out["home"]["qb1"]["name"] == "Home QB"


def test_unverified_event_still_fails_closed_and_strips_identity():
    resolved = _resolved()
    snapshot = {
        "ready": False,
        "state": "UNVERIFIED",
        "prop_gate_open": False,
        "reason": "exact ESPN event summary unavailable",
        "team_by_id": {},
    }

    out = guard_passing_identity(
        {"game_id": "401999999"},
        resolved,
        snapshot_loader=lambda event_id: snapshot,
        roster_loader=lambda abbr: (set(), {"ok": False}),
    )

    assert out["step7_app_identity_verified"] is False
    assert out["away"]["identity_verified"] is False
    assert out["away"]["qb1"] == {}
    assert out["home"]["identity_verified"] is False
    assert out["home"]["qb1"] == {}
