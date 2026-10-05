from __future__ import annotations

from devsystem import nfl_live_game_repair_step3_rushing_live_v1 as cert


def test_step3_is_rushing_only_and_proof_only():
    assert cert.MISSION_STEP == "3/5"
    assert cert.RUSHING_OWNER == "nfl_rushing_yards_hub_v16.py"
    assert cert.RECEIVING_OWNER == "nfl_receiving_yards_hub_v17.py"
    assert cert.MAY_MODIFY_RUSHING_PAGE is False
    assert cert.MAY_MODIFY_RECEIVING_PAGE is False
    assert cert.MAY_MODIFY_ROUTER is False
    assert cert.MAY_MODIFY_PROJECTION is False
    assert cert.MAY_MODIFY_PROBABILITY is False
    assert cert.MAY_MODIFY_RANKING is False
    assert cert.MAY_MODIFY_SPORTSBOOK is False
    assert cert.API2_USED is False


def test_step3_repository_contract_has_no_second_rushing_kickoff_gate():
    result = cert.verify_repository_contract()
    assert result["status"] == "GREEN"
    assert result["router_owner"] == "nfl_rushing_yards_hub_v16"
    assert result["shared_guard_called"] is True
    assert result["context_api_state_agnostic"] is True
    assert result["base_renderer_consumes_ready_data"] is True
    assert result["receiving_untouched"] is True


def test_step3_synthetic_live_rushing_path_stays_visible():
    result = cert.certify_synthetic_live_rushing()
    assert result["status"] == "GREEN"
    assert result["ready"] is True
    assert result["data_available"] is True
    assert result["identity_state"] == "LIVE"
    assert result["live_identity_verified"] is True
    assert result["prop_market_open"] is False
    assert result["team_count"] == 2
    assert result["player_count"] >= 2


def test_step3_final_game_still_fails_closed():
    result = cert.certify_synthetic_final_rushing()
    assert result["status"] == "GREEN"
    assert result["ready"] is False
    assert result["team_count"] == 0


def test_step3_stale_roster_identity_still_fails_closed():
    result = cert.certify_synthetic_stale_roster_rushing()
    assert result["status"] == "GREEN"
    assert result["ready"] is False
    assert result["identity_verified"] is False


def test_step3_live_rushing_filters_only_stale_api_player_ids(monkeypatch):
    import nfl_prop_app_eligibility_v1 as gate
    import nfl_rushing_yards_hub_v16 as rushing

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
                        "position": "RB",
                        "player_name": "Current ATL Runner",
                    },
                    {
                        "official_athlete_id": "999",
                        "official_team_id": "1",
                        "position": "RB",
                        "player_name": "Stale API Runner",
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
                        "position": "RB",
                        "player_name": "Current CAR Runner",
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

    monkeypatch.setattr(rushing, "_ORIGINAL_LOAD", lambda _event_id: payload)
    monkeypatch.setattr(gate, "_load_event_snapshot", lambda _event_id: snapshot)
    monkeypatch.setattr(
        gate,
        "_eligible_ids_for_team",
        lambda abbr: (set(current[abbr]), {"ok": True, "http": 200}),
    )

    result = rushing._load_rushing_context_step7("401000001")
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
    assert result["step3_live_roster_filtered_count"] == 1
