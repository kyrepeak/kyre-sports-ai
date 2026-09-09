"""Regression tests for CFB O/U deep current-data reconciliation."""
from __future__ import annotations

import cfb_over_under_deep_data_reconciliation_v1 as deep


def _summary():
    return {
        "header": {
            "id": "401858213",
            "week": 2,
            "competitions": [{
                "id": "401858213",
                "neutralSite": False,
                "competitors": [
                    {
                        "homeAway": "away",
                        "team": {"id": "50"},
                        "records": [
                            {"type": "total", "summary": "1-1"},
                            {"type": "vsconf", "summary": "0-0"},
                        ],
                    },
                    {
                        "homeAway": "home",
                        "team": {"id": "2390"},
                        "curatedRank": {"current": 7},
                        "records": [
                            {"type": "total", "summary": "1-0"},
                            {"type": "vsconf", "summary": "1-0"},
                        ],
                    },
                ],
                "status": {
                    "type": {
                        "description": "Scheduled",
                        "detail": "Thu, September 10th at 8:00 PM EDT",
                    }
                },
                "broadcasts": [{
                    "media": {"shortName": "ACC Network"}
                }],
            }],
        },
        "gameInfo": {
            "venue": {
                "fullName": "Hard Rock Stadium",
                "grass": True,
                "address": {"city": "Miami Gardens", "state": "FL"},
            }
        },
    }


def test_summary_extracts_exact_records_and_game_metadata():
    summary = _summary()
    away = deep._team_snapshot_from_summary(summary, "away")
    home = deep._team_snapshot_from_summary(summary, "home")
    assert away["overall_record"] == "1-1"
    assert away["conference_record"] == "0-0"
    assert home["overall_record"] == "1-0"
    assert home["conference_record"] == "1-0"
    assert home["curated_rank"] == 7

    game = deep._enrich_game(
        {"game_date": "2026-09-10"},
        summary,
        {"event_id": "401858213"},
    )
    assert game["venue"] == "Hard Rock Stadium"
    assert game["broadcast"] == "ACC Network"
    assert game["status"] == "Scheduled"
    assert game["espn_week"] == 2
    assert game["home_record_summary"] == "1-0"
    assert game["away_record_summary"] == "1-1"


def test_reconcile_profile_repairs_record_splits_recent_coach_and_polls(monkeypatch):
    rows = [
        {
            "event_id": "a",
            "date": "2026-09-05T00:00Z",
            "points_for": 45.0,
            "points_against": 6.0,
            "opponent_name": "Stanford",
            "opponent_id": "24",
            "location": "away",
            "opponent_record_pct": 0.0,
        }
    ]
    monkeypatch.setattr(
        deep,
        "_current_rows",
        lambda *a, **k: (rows, {"fallback_resolved": 1}, []),
    )
    monkeypatch.setattr(
        deep,
        "_head_coach",
        lambda *a, **k: ({
            "ready": True,
            "id": "559987",
            "name": "Mario Cristobal",
            "source": "ESPN Core current-season head coach",
        }, []),
    )
    monkeypatch.setattr(
        deep,
        "_team_polls",
        lambda *a, **k: ({
            "ap": {"rank": 7},
            "coaches": {"rank": 7},
        }, []),
    )
    profile = {
        "team": "Miami (FL)",
        "record_text": "1 GAME SAMPLE • W-L UNAVAILABLE",
        "record": {"games": 1},
        "division_context": "FBS",
        "data_quality": {},
        "data_source": "NCAA stats",
    }
    game = {
        "game_date": "2026-09-10",
        "kickoff_iso": "2026-09-11T00:00:00Z",
        "espn_week": 2,
    }
    out, diag = deep._reconcile_profile(
        "home",
        game,
        profile,
        _summary(),
        {"event_id": "401858213", "home_espn_team_id": "2390"},
    )
    assert out["record_text"] == "1-0"
    assert out["home_record"] == {"wins": 0, "losses": 0, "ties": 0, "games": 0}
    assert out["away_record"]["wins"] == 1
    assert out["recent_form"] == "W"
    assert out["ppg"] == 45.0
    assert out["points_allowed_pg"] == 6.0
    assert out["head_coach"] == "Mario Cristobal"
    assert out["ap_rank"] == 7
    assert out["coaches_poll_rank"] == 7
    assert diag["schedule_games"] == 1


def test_fcs_profile_marks_fbs_polls_not_applicable(monkeypatch):
    monkeypatch.setattr(
        deep,
        "_current_rows",
        lambda *a, **k: ([], {}, []),
    )
    monkeypatch.setattr(
        deep,
        "_head_coach",
        lambda *a, **k: ({
            "ready": True,
            "id": "560272",
            "name": "Quinn Gray Sr.",
            "source": "ESPN Core current-season head coach",
        }, []),
    )
    monkeypatch.setattr(deep, "_team_polls", lambda *a, **k: ({}, []))
    profile = {
        "team": "Florida A&M",
        "record_text": "2 GAME SAMPLE • W-L UNAVAILABLE",
        "record": {"games": 2},
        "division_context": "FCS",
        "data_quality": {},
        "data_source": "NCAA FCS stats",
    }
    out, _ = deep._reconcile_profile(
        "away",
        {
            "game_date": "2026-09-10",
            "kickoff_iso": "2026-09-11T00:00:00Z",
            "espn_week": 2,
        },
        profile,
        _summary(),
        {"event_id": "401858213", "away_espn_team_id": "50"},
    )
    assert out["record_text"] == "1-1"
    assert out["ap_rank"] is None
    assert "not applicable" in out["rank_source"].lower()
    assert out["head_coach"] == "Quinn Gray Sr."


def test_record_parser_never_turns_sample_count_into_wl():
    assert deep._parse_record("1-0")["games"] == 1
    assert deep._parse_record("1-1")["games"] == 2
    assert deep._parse_record("2 GAME SAMPLE • W-L UNAVAILABLE") == {}
