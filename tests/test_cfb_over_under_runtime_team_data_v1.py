"""Regression tests for the central runtime team-data adapter."""
from __future__ import annotations

import cfb_over_under_runtime_team_data_v1 as runtime


def _stale_profiles():
    return {
        "away": {
            "team": "Florida A&M",
            "conference": "SWAC",
            "division_context": "FCS",
            "record_text": "0-0",
            "record": {"games": 0},
            "home_record": {},
            "away_record": {},
            "recent_form": "—",
            "ppg": 16.5,
            "points_allowed_pg": 19.0,
            "official_stats": {},
        },
        "home": {
            "team": "Miami (FL)",
            "conference": "ACC",
            "division_context": "FBS",
            "record_text": "0-0",
            "record": {"games": 0},
            "home_record": {},
            "away_record": {},
            "recent_form": "—",
            "ppg": 45.0,
            "points_allowed_pg": 6.0,
            "official_stats": {},
            "ap_rank": None,
        },
    }


def _snapshot():
    return {
        "event_id": "401858213",
        "game_date": "2026-09-10",
        "venue": "Hard Rock Stadium",
        "broadcast": "ACC Network",
        "status": "Scheduled",
        "espn_week": 2,
        "away": {
            "team_id": "50",
            "record_text": "1-1",
            "conference_record_text": "0-0",
            "home_record": {"wins": 1, "losses": 0, "ties": 0, "games": 1},
            "away_record": {"wins": 0, "losses": 0, "ties": 0, "games": 0},
            "neutral_record": {"wins": 0, "losses": 1, "ties": 0, "games": 1},
            "recent_form": "WL",
            "ppg": 16.5,
            "points_allowed_pg": 19.0,
            "head_coach": "Quinn Gray Sr.",
            "division_context": "FCS",
            "ap_rank": None,
            "coaches_poll_rank": None,
        },
        "home": {
            "team_id": "2390",
            "record_text": "1-0",
            "conference_record_text": "1-0",
            "home_record": {"wins": 0, "losses": 0, "ties": 0, "games": 0},
            "away_record": {"wins": 1, "losses": 0, "ties": 0, "games": 1},
            "neutral_record": {"wins": 0, "losses": 0, "ties": 0, "games": 0},
            "recent_form": "W",
            "ppg": 45.0,
            "points_allowed_pg": 6.0,
            "head_coach": "Mario Cristobal",
            "division_context": "FBS",
            "ap_rank": 7,
            "coaches_poll_rank": 7,
        },
    }


def test_snapshot_fallback_corrects_stale_profiles_even_when_live_reconcile_fails(monkeypatch):
    monkeypatch.setattr(
        runtime.frozen,
        "load_matchup_team_data",
        lambda game, day: (_stale_profiles(), {"attempts": []}),
    )
    monkeypatch.setattr(
        runtime.deep,
        "reconcile_matchup",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("provider blocked")),
    )
    monkeypatch.setattr(runtime, "_find_snapshot", lambda game: _snapshot())

    game = {
        "game_date": "2026-09-10",
        "away_team": "Florida A&M",
        "home_team": "Miami (FL)",
        "venue": "Venue unavailable",
        "broadcast": "Broadcast unavailable",
    }

    game2, away, home, diag = runtime.reconcile_runtime(game, "2026-09-10")

    assert game2["espn_event_id"] == "401858213"
    assert game2["venue"] == "Hard Rock Stadium"
    assert game2["broadcast"] == "ACC Network"
    assert game["venue"] == "Hard Rock Stadium"
    assert away["record_text"] == "1-1"
    assert away["recent_form"] == "WL"
    assert away["head_coach"] == "Quinn Gray Sr."
    assert home["record_text"] == "1-0"
    assert home["ap_rank"] == 7
    assert home["coaches_poll_rank"] == 7
    assert home["head_coach"] == "Mario Cristobal"
    assert diag["runtime_snapshot_used"] is True
    assert diag["runtime_status"] == "GREEN"
    assert diag["deep_reconciliation_error"] == ""


def test_no_snapshot_exposes_live_failure_instead_of_silent_stale_fallback(monkeypatch):
    monkeypatch.setattr(
        runtime.frozen,
        "load_matchup_team_data",
        lambda game, day: (_stale_profiles(), {"attempts": []}),
    )
    monkeypatch.setattr(runtime, "_find_snapshot", lambda game: {})
    monkeypatch.setattr(
        runtime.deep,
        "reconcile_matchup",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("provider blocked")),
    )

    _, away, home, diag = runtime.reconcile_runtime(
        {
            "game_date": "2026-09-10",
            "away_team": "A",
            "home_team": "B",
            "venue": "Venue unavailable",
            "broadcast": "Broadcast unavailable",
        },
        "2026-09-10",
    )

    assert away["record_text"] == "0-0"
    assert home["record_text"] == "0-0"
    assert diag["runtime_status"] == "PARTIAL"
    assert "RuntimeError: provider blocked" in diag["deep_reconciliation_error"]
    assert "venue unavailable" in diag["runtime_issues"]


def test_event_record_fallback_repairs_profile_without_snapshot():
    out = runtime._apply_game_event_fallback(
        {
            "record_text": "0-0",
            "record": {"games": 0},
            "division_context": "FBS",
            "ap_rank": None,
        },
        {
            "home_record_summary": "1-0",
            "home_rank": 7,
            "home_espn_team_id": "2390",
        },
        "home",
    )
    assert out["record_text"] == "1-0"
    assert out["record"]["wins"] == 1
    assert out["ap_rank"] == 7
    assert out["espn_team_id"] == "2390"
