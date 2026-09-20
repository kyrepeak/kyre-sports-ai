from __future__ import annotations

import nfl_game_day_availability_v1 as game_day


def _row(name: str, status: str, athlete_id: str) -> dict:
    return {"name": name, "status": status, "athlete_id": athlete_id}


def test_pregame_without_explicit_inactives_stays_pending() -> None:
    event_map = {
        "CAR": [_row("Panther One", "Questionable", "1")],
        "ATL": [_row("Falcon One", "Out", "2")],
    }
    snap = game_day.event_availability_snapshot(
        "401872933", "CAR", "ATL", "pre",
        event_map=event_map, event_diag={"ok": True, "http": 200},
    )
    assert snap["state"] == "PENDING"
    assert snap["prop_gate_open"] is False


def test_explicit_inactives_confirm_pregame() -> None:
    event_map = {
        "CAR": [_row("Panther One", "Inactive", "1")],
        "ATL": [_row("Michael Penix Jr.", "Inactive", "2")],
    }
    snap = game_day.event_availability_snapshot(
        "401872933", "CAR", "ATL", "pre",
        event_map=event_map, event_diag={"ok": True, "http": 200},
    )
    assert snap["state"] == "CONFIRMED"
    assert snap["prop_gate_open"] is True


def test_live_event_requires_both_team_unavailable_coverage() -> None:
    good = {
        "CAR": [_row("Panther One", "Out", "1")],
        "ATL": [_row("Michael Penix Jr.", "Out", "2")],
    }
    snap = game_day.event_availability_snapshot(
        "401872933", "CAR", "ATL", "in",
        event_map=good, event_diag={"ok": True, "http": 200},
    )
    assert snap["state"] == "CONFIRMED"

    missing = {"ATL": [_row("Michael Penix Jr.", "Out", "2")]}
    snap2 = game_day.event_availability_snapshot(
        "401872933", "CAR", "ATL", "in",
        event_map=missing, event_diag={"ok": True, "http": 200},
    )
    assert snap2["state"] == "PENDING"
    assert snap2["prop_gate_open"] is False


def test_provider_failure_is_unverified() -> None:
    snap = game_day.event_availability_snapshot(
        "401872933", "CAR", "ATL", "pre",
        event_map={}, event_diag={"ok": False, "http": 503},
    )
    assert snap["state"] == "UNVERIFIED"
    assert snap["prop_gate_open"] is False
