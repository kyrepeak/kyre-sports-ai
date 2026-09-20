from __future__ import annotations

import nfl_prop_app_eligibility_v1 as guard


def _snapshot(open_gate: bool = True, state: str = "CONFIRMED"):
    return {
        "ready": True,
        "state": state,
        "prop_gate_open": open_gate,
        "reason": "" if open_gate else "not verified",
        "team_by_id": {"1": "ATL", "29": "CAR"},
    }


def _roster_loader(abbr: str):
    rows = {
        "ATL": {"101", "102"},
        "CAR": {"201", "202"},
    }
    return rows.get(abbr, set()), {"ok": True, "http": 200}


def _context():
    return {
        "ready": True,
        "data_available": True,
        "official_event_id": "401000001",
        "teams": [
            {
                "official_team_id": "1",
                "team_abbreviation": "ATL",
                "players": [
                    {
                        "official_athlete_id": "101",
                        "official_team_id": "1",
                        "position": "RB",
                        "player_name": "Current ATL",
                    }
                ],
            },
            {
                "official_team_id": "29",
                "team_abbreviation": "CAR",
                "players": [
                    {
                        "official_athlete_id": "201",
                        "official_team_id": "29",
                        "position": "WR",
                        "player_name": "Current CAR",
                    }
                ],
            },
        ],
    }


def test_context_fails_closed_when_game_day_gate_is_not_open():
    result = guard.guard_context_payload(
        _context(),
        "401000001",
        allowed_positions={"RB", "WR"},
        snapshot_loader=lambda _event: _snapshot(False, "PENDING"),
        roster_loader=_roster_loader,
    )
    assert result["ready"] is False
    assert result["teams"] == []
    assert result["step7_app_identity_verified"] is False


def test_context_fails_closed_on_one_stale_player_id():
    payload = _context()
    payload["teams"][0]["players"][0]["official_athlete_id"] = "999"
    result = guard.guard_context_payload(
        payload,
        "401000001",
        allowed_positions={"RB", "WR"},
        snapshot_loader=lambda _event: _snapshot(),
        roster_loader=_roster_loader,
    )
    assert result["ready"] is False
    assert result["teams"] == []
    assert "current-roster" in result["reason"]


def test_context_preserves_only_exact_id_verified_payload():
    result = guard.guard_context_payload(
        _context(),
        "401000001",
        allowed_positions={"RB", "WR"},
        snapshot_loader=lambda _event: _snapshot(),
        roster_loader=_roster_loader,
    )
    assert result["ready"] is True
    assert result["step7_app_identity_verified"] is True
    assert result["teams"][0]["players"][0]["step7_app_identity_verified"] is True
    assert result["teams"][1]["players"][0]["step7_app_identity_verified"] is True


def _passing_result():
    return {
        "ready": True,
        "identity_ready": True,
        "prop_availability_ready": True,
        "game_id": "401000001",
        "away": {
            "team_id": "1",
            "abbr": "ATL",
            "identity_verified": True,
            "qbs": [{"athlete_id": "101", "name": "Current ATL"}],
            "qb1": {"athlete_id": "101", "name": "Current ATL"},
        },
        "home": {
            "team_id": "29",
            "abbr": "CAR",
            "identity_verified": True,
            "qbs": [{"athlete_id": "201", "name": "Current CAR"}],
            "qb1": {"athlete_id": "201", "name": "Current CAR"},
        },
    }


def test_passing_identity_is_stripped_when_current_roster_changes():
    def roster(abbr: str):
        if abbr == "ATL":
            return {"999"}, {"ok": True}
        return {"201"}, {"ok": True}

    result = guard.guard_passing_identity(
        {"game_id": "401000001"},
        _passing_result(),
        snapshot_loader=lambda _event: _snapshot(),
        roster_loader=roster,
    )
    assert result["ready"] is False
    assert result["away"]["qb1"] == {}
    assert result["home"]["qb1"] == {}
    assert result["away"]["qbs"] == []
    assert result["home"]["qbs"] == []


def test_passing_identity_stays_green_on_exact_current_ids():
    result = guard.guard_passing_identity(
        {"game_id": "401000001"},
        _passing_result(),
        snapshot_loader=lambda _event: _snapshot(),
        roster_loader=_roster_loader,
    )
    assert result["ready"] is True
    assert result["step7_app_identity_verified"] is True
    assert result["away"]["qb1"]["athlete_id"] == "101"
    assert result["home"]["qb1"]["athlete_id"] == "201"
