from __future__ import annotations

import sys
from types import ModuleType

import nfl_prop_app_eligibility_v1 as guard


def _summary(state: str) -> dict:
    return {
        "header": {
            "id": "401000001",
            "competitions": [
                {
                    "id": "401000001",
                    "status": {"type": {"state": state}},
                    "competitors": [
                        {
                            "homeAway": "away",
                            "team": {"id": "1", "abbreviation": "ATL"},
                        },
                        {
                            "homeAway": "home",
                            "team": {"id": "29", "abbreviation": "CAR"},
                        },
                    ],
                }
            ],
        }
    }


def _context() -> dict:
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


def _roster_loader(abbr: str):
    rows = {
        "ATL": {"101"},
        "CAR": {"201"},
    }
    return rows.get(abbr, set()), {"ok": True, "http": 200}


def _install_snapshot_modules(monkeypatch, state: str) -> None:
    nfl_data = ModuleType("nfl_moneyline_hub_v2")
    nfl_data.ESPN_BASE = "https://example.test"
    nfl_data._json_get = lambda _url: (_summary(state), {"ok": True, "http": 200})
    nfl_data._parse_injuries = lambda _payload: {}

    game_day = ModuleType("nfl_game_day_availability_v1")
    game_day.event_availability_snapshot = lambda *_args, **_kwargs: {
        "state": "UNVERIFIED",
        "prop_gate_open": False,
    }
    game_day.current_prop_eligible_keys = lambda _abbr: (set(), {}, {"ok": False})

    monkeypatch.setitem(sys.modules, "nfl_moneyline_hub_v2", nfl_data)
    monkeypatch.setitem(sys.modules, "nfl_game_day_availability_v1", game_day)


def test_live_event_snapshot_opens_identity_bridge_without_reopening_market_gate(monkeypatch):
    _install_snapshot_modules(monkeypatch, "in")

    snapshot = guard._load_event_snapshot("401000001")

    assert snapshot["ready"] is True
    assert snapshot["state"] == "CLOSED"
    assert snapshot["identity_state"] == "LIVE"
    assert snapshot["identity_gate_open"] is True
    assert snapshot["prop_gate_open"] is False


def test_live_identity_bridge_keeps_exact_current_roster_context_visible():
    snapshot = {
        "ready": True,
        "state": "CLOSED",
        "identity_state": "LIVE",
        "identity_gate_open": True,
        "prop_gate_open": False,
        "reason": "pregame player-prop market gate closed after kickoff",
        "team_by_id": {"1": "ATL", "29": "CAR"},
    }

    result = guard.guard_context_payload(
        _context(),
        "401000001",
        allowed_positions={"RB", "WR"},
        snapshot_loader=lambda _event: snapshot,
        roster_loader=_roster_loader,
    )

    assert result["ready"] is True
    assert result["step7_app_identity_verified"] is True
    assert result["step7_app_identity_state"] == "LIVE"
    assert result["step7_app_live_identity_verified"] is True
    assert result["step7_app_final_inactives_verified"] is False
    assert result["teams"][0]["players"][0]["official_athlete_id"] == "101"
    assert result["teams"][1]["players"][0]["official_athlete_id"] == "201"


def test_final_event_stays_fail_closed_for_rushing_and_receiving_context(monkeypatch):
    _install_snapshot_modules(monkeypatch, "post")

    snapshot = guard._load_event_snapshot("401000001")
    result = guard.guard_context_payload(
        _context(),
        "401000001",
        allowed_positions={"RB", "WR"},
        snapshot_loader=lambda _event: snapshot,
        roster_loader=_roster_loader,
    )

    assert snapshot["state"] == "CLOSED"
    assert snapshot.get("identity_gate_open") is not True
    assert result["ready"] is False
    assert result["teams"] == []
    assert result["step7_app_identity_verified"] is False
