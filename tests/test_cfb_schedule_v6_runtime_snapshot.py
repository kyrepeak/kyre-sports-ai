"""Regression tests for additive Schedule V6 FBS + FCS snapshot enrichment."""
from __future__ import annotations

import cfb_schedule_v6_runtime_snapshot as schedule


def test_v6_finds_snapshot_by_exact_official_event_id(monkeypatch):
    monkeypatch.setattr(
        schedule,
        "_load_v2_snapshot",
        lambda: {
            "version": 2,
            "games": [
                {
                    "event_id": "401858213",
                    "game_date": "2026-09-10",
                    "away_team": "Florida A&M",
                    "home_team": "Miami",
                }
            ],
        },
    )
    row = schedule._find_v2_snapshot(
        {
            "espn_event_id": "401858213",
            "game_date": "2026-09-10",
            "away_team": "Florida A&M",
            "home_team": "Miami (FL)",
        }
    )
    assert row["event_id"] == "401858213"


def test_v6_can_recover_missing_official_id_by_exact_date_team_identity(monkeypatch):
    monkeypatch.setattr(
        schedule,
        "_load_v2_snapshot",
        lambda: {
            "version": 2,
            "games": [
                {
                    "event_id": "fcs-123",
                    "game_date": "2026-09-12",
                    "away_team": "Albany",
                    "home_team": "New Hampshire",
                }
            ],
        },
    )
    row = schedule._find_v2_snapshot(
        {
            "game_date": "2026-09-12",
            "away_team": "Albany",
            "home_team": "New Hampshire",
        }
    )
    assert row["event_id"] == "fcs-123"


def test_v6_is_additive_over_frozen_v5():
    assert schedule.FROZEN_SCHEDULE == "cfb_schedule_v5_runtime_snapshot"
    assert "FBS + FCS" in schedule.MODEL_VERSION
