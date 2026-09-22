"""Regression tests for snapshot-backed Schedule V5."""
from __future__ import annotations

import cfb_schedule_v5_runtime_snapshot as schedule


def test_snapshot_turns_zero_runtime_enrichment_into_verified_match(monkeypatch):
    game = {
        "game_date": "2026-09-10",
        "away_team": "Florida A&M",
        "home_team": "Miami (FL)",
        "venue": "Venue unavailable",
        "broadcast": "Broadcast unavailable",
    }
    monkeypatch.setattr(
        schedule.frozen,
        "load_with_diagnostics",
        lambda day: ([game], {
            "games": 1,
            "identity_ready": True,
            "espn_matches": 0,
            "venue_missing": 1,
            "broadcast_missing": 1,
        }),
    )
    monkeypatch.setattr(
        schedule.runtime_data,
        "_find_snapshot",
        lambda game: {
            "event_id": "401858213",
            "venue": "Hard Rock Stadium",
            "broadcast": "ACC Network",
            "status": "Scheduled",
            "espn_week": 2,
            "away": {"team_id": "50", "record_text": "1-1"},
            "home": {"team_id": "2390", "record_text": "1-0", "ap_rank": 7},
        },
    )

    rows, diag = schedule.load_with_diagnostics.__wrapped__("2026-09-10")
    assert rows[0]["venue"] == "Hard Rock Stadium"
    assert rows[0]["broadcast"] == "ACC Network"
    assert rows[0]["home_record_summary"] == "1-0"
    assert rows[0]["home_rank"] == 7
    assert diag["runtime_snapshot_matches"] == 1
    assert diag["espn_matches"] == 1
    assert diag["venue_missing"] == 0
    assert diag["broadcast_missing"] == 0
