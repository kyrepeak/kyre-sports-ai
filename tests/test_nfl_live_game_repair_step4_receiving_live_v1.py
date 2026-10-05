from __future__ import annotations


def test_step4_live_receiving_filters_only_stale_api_player_ids(monkeypatch):
    import nfl_prop_app_eligibility_v1 as gate
    import nfl_receiving_yards_hub_v17 as receiving

    payload = {
        "ready": True,
        "data_available": True,
        "official_event_id": "401000001",
        "market_enabled": False,
        "sportsbook_influence": 0.0,
        "teams": [
            {
                "official_team_id": "1",
                "team_abbreviation": "ATL",
                "players": [
                    {
                        "official_athlete_id": "101",
                        "official_team_id": "1",
                        "position": "WR",
                        "player_name": "Current ATL Receiver",
                    },
                    {
                        "official_athlete_id": "999",
                        "official_team_id": "1",
                        "position": "WR",
                        "player_name": "Stale API Receiver",
                    },
                ],
            },
            {
                "official_team_id": "29",
                "team_abbreviation": "CAR",
                "players": [
                    {
                        "official_athlete_id": "201",
                        "official_team_id": "29",
                        "position": "TE",
                        "player_name": "Current CAR Receiver",
                    }
                ],
            },
        ],
    }
    snapshot = {
        "ready": True,
        "state": "CLOSED",
        "identity_state": "LIVE",
        "identity_gate_open": True,
        "prop_gate_open": False,
        "reason": "pregame player-prop identity closed after kickoff",
        "team_by_id": {"1": "ATL", "29": "CAR"},
    }
    current = {"ATL": {"101"}, "CAR": {"201"}}

    monkeypatch.setattr(receiving, "_ORIGINAL_LOAD", lambda _event_id: payload)
    monkeypatch.setattr(gate, "_load_event_snapshot", lambda _event_id: snapshot)
    monkeypatch.setattr(
        gate,
        "_eligible_ids_for_team",
        lambda abbr: (set(current[abbr]), {"ok": True, "http": 200}),
    )

    result = receiving._load_receiving_context_step7("401000001")
    assert result["ready"] is True
    assert result["data_available"] is True
    assert result["step7_app_identity_state"] == "LIVE"
    assert result["step7_app_live_identity_verified"] is True
    player_ids = {
        player["official_athlete_id"]
        for team in result["teams"]
        for player in team["players"]
    }
    assert player_ids == {"101", "201"}
    assert result["step4_live_roster_filtered_count"] == 1


def test_step4_malformed_receiving_identity_still_fails_closed(monkeypatch):
    import nfl_prop_app_eligibility_v1 as gate
    import nfl_receiving_yards_hub_v17 as receiving

    payload = {
        "ready": True,
        "data_available": True,
        "official_event_id": "401000001",
        "market_enabled": False,
        "sportsbook_influence": 0.0,
        "teams": [
            {
                "official_team_id": "1",
                "team_abbreviation": "ATL",
                "players": [{
                    "official_athlete_id": "not-an-id",
                    "official_team_id": "1",
                    "position": "WR",
                    "player_name": "Malformed Receiver",
                }],
            },
            {
                "official_team_id": "29",
                "team_abbreviation": "CAR",
                "players": [{
                    "official_athlete_id": "201",
                    "official_team_id": "29",
                    "position": "TE",
                    "player_name": "Current CAR Receiver",
                }],
            },
        ],
    }
    snapshot = {
        "ready": True,
        "state": "CLOSED",
        "identity_state": "LIVE",
        "identity_gate_open": True,
        "prop_gate_open": False,
        "reason": "pregame player-prop identity closed after kickoff",
        "team_by_id": {"1": "ATL", "29": "CAR"},
    }
    current = {"ATL": {"101"}, "CAR": {"201"}}

    monkeypatch.setattr(receiving, "_ORIGINAL_LOAD", lambda _event_id: payload)
    monkeypatch.setattr(gate, "_load_event_snapshot", lambda _event_id: snapshot)
    monkeypatch.setattr(
        gate,
        "_eligible_ids_for_team",
        lambda abbr: (set(current[abbr]), {"ok": True, "http": 200}),
    )

    result = receiving._load_receiving_context_step7("401000001")
    assert result["ready"] is False
    assert result["teams"] == []
    assert result["step7_app_identity_verified"] is False


def test_step4_team_mismatched_numeric_identity_still_fails_closed(monkeypatch):
    import nfl_prop_app_eligibility_v1 as gate
    import nfl_receiving_yards_hub_v17 as receiving

    payload = {
        "ready": True,
        "data_available": True,
        "official_event_id": "401000001",
        "market_enabled": False,
        "sportsbook_influence": 0.0,
        "teams": [
            {
                "official_team_id": "1",
                "team_abbreviation": "ATL",
                "players": [
                    {
                        "official_athlete_id": "999",
                        "official_team_id": "29",
                        "position": "WR",
                        "player_name": "Wrong-Team Numeric Receiver",
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
                        "position": "TE",
                        "player_name": "Current CAR Receiver",
                    }
                ],
            },
        ],
    }
    snapshot = {
        "ready": True,
        "state": "CLOSED",
        "identity_state": "LIVE",
        "identity_gate_open": True,
        "prop_gate_open": False,
        "reason": "pregame player-prop identity closed after kickoff",
        "team_by_id": {"1": "ATL", "29": "CAR"},
    }
    current = {"ATL": {"101"}, "CAR": {"201"}}

    monkeypatch.setattr(receiving, "_ORIGINAL_LOAD", lambda _event_id: payload)
    monkeypatch.setattr(gate, "_load_event_snapshot", lambda _event_id: snapshot)
    monkeypatch.setattr(
        gate,
        "_eligible_ids_for_team",
        lambda abbr: (set(current[abbr]), {"ok": True, "http": 200}),
    )

    result = receiving._load_receiving_context_step7("401000001")
    assert result["ready"] is False
    assert result["teams"] == []
    assert result["step7_app_identity_verified"] is False
