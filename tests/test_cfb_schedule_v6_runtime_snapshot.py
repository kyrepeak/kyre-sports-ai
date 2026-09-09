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


def test_v6_prefers_exact_team_ids_when_event_id_is_missing(monkeypatch):
    monkeypatch.setattr(
        schedule,
        "_load_v2_snapshot",
        lambda: {
            "version": 2,
            "games": [
                {
                    "event_id": "miami-fl",
                    "game_date": "2026-09-12",
                    "away_team": "Other",
                    "home_team": "Miami",
                    "away": {"team_id": "1"},
                    "home": {"team_id": "2390"},
                },
                {
                    "event_id": "miami-oh",
                    "game_date": "2026-09-12",
                    "away_team": "Other",
                    "home_team": "Miami (OH)",
                    "away": {"team_id": "1"},
                    "home": {"team_id": "193"},
                },
            ],
        },
    )
    row = schedule._find_v2_snapshot(
        {
            "game_date": "2026-09-12",
            "away_team": "Other",
            "home_team": "Miami (OH)",
            "away_espn_team_id": "1",
            "home_espn_team_id": "193",
        }
    )
    assert row["event_id"] == "miami-oh"


def test_v6_name_alias_collision_fails_closed(monkeypatch):
    monkeypatch.setattr(
        schedule,
        "_load_v2_snapshot",
        lambda: {
            "version": 2,
            "games": [
                {
                    "event_id": "miami-fl",
                    "game_date": "2026-09-12",
                    "away_team": "Other",
                    "home_team": "Miami",
                },
                {
                    "event_id": "miami-oh",
                    "game_date": "2026-09-12",
                    "away_team": "Other",
                    "home_team": "Miami (OH)",
                },
            ],
        },
    )
    row = schedule._find_v2_snapshot(
        {
            "game_date": "2026-09-12",
            "away_team": "Other",
            "home_team": "Miami (FL)",
        }
    )
    assert row == {}
