"""Regression tests for additive Schedule V6 FBS + FCS snapshot enrichment."""
from __future__ import annotations

import json

import cfb_schedule_v6_runtime_snapshot as schedule





class _FakeSnapshotResponse:
    def __init__(self, payload, *, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code != 200:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _complete_snapshot_row(event_id="401858213"):
    return {
        "event_id": event_id,
        "game_date": "2026-09-10",
        "away_team": "Florida A&M",
        "home_team": "Miami",
        "away": {"team_id": "50"},
        "home": {"team_id": "2390"},
    }


def test_v6_prefers_valid_certified_runtime_branch_snapshot(monkeypatch):
    remote = {
        "version": 2,
        "games": [_complete_snapshot_row("remote-event")],
    }
    monkeypatch.setattr(
        schedule.requests,
        "get",
        lambda *args, **kwargs: _FakeSnapshotResponse(remote),
    )

    schedule._load_v2_snapshot.clear()
    payload = schedule._load_v2_snapshot()
    schedule._load_v2_snapshot.clear()

    assert payload["games"][0]["event_id"] == "remote-event"
    assert payload["_runtime_snapshot_source"] == "certified-runtime-branch"


def test_v6_rejects_ambiguous_remote_snapshot_and_falls_back_local(
    monkeypatch,
    tmp_path,
):
    duplicate = _complete_snapshot_row("duplicate-event")
    remote = {
        "version": 2,
        "games": [duplicate, dict(duplicate)],
    }
    local = {
        "version": 2,
        "games": [_complete_snapshot_row("local-event")],
    }
    local_path = tmp_path / "cfb_runtime_snapshot_v2.json"
    local_path.write_text(json.dumps(local), encoding="utf-8")

    monkeypatch.setattr(schedule, "SNAPSHOT_PATH", local_path)
    monkeypatch.setattr(
        schedule.requests,
        "get",
        lambda *args, **kwargs: _FakeSnapshotResponse(remote),
    )

    schedule._load_v2_snapshot.clear()
    payload = schedule._load_v2_snapshot()
    schedule._load_v2_snapshot.clear()

    assert payload["games"][0]["event_id"] == "local-event"
    assert payload["_runtime_snapshot_source"] == "checked-in-main-fallback"


def test_v6_runtime_snapshot_validator_requires_complete_official_identity():
    incomplete = {
        "version": 2,
        "games": [
            {
                "event_id": "401858213",
                "game_date": "2026-09-10",
                "away_team": "Florida A&M",
                "home_team": "Miami",
                "away": {"team_id": ""},
                "home": {"team_id": "2390"},
            }
        ],
    }
    assert (
        schedule._validated_v2_snapshot(
            incomplete,
            source="certified-runtime-branch",
        )
        is None
    )


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

def _clear_v6_cache():
    for fn in (schedule.load_with_diagnostics, schedule.games_for_date):
        try:
            fn.clear()
        except Exception:
            pass


def test_v6_seeds_verified_snapshot_when_frozen_v5_returns_zero_games(monkeypatch):
    snapshot = {
        "version": 2,
        "games": [
            {
                "event_id": "401858213",
                "game_date": "2026-09-10",
                "away_team": "Florida A&M",
                "home_team": "Miami",
                "venue": "Hard Rock Stadium",
                "broadcast": "ACC Network",
                "status": "Scheduled",
                "espn_week": 2,
                "away": {
                    "team_id": "50",
                    "record_text": "1-1",
                    "ap_rank": None,
                },
                "home": {
                    "team_id": "2390",
                    "record_text": "1-0",
                    "ap_rank": 7,
                },
            },
            {
                "event_id": "other-date",
                "game_date": "2026-09-11",
                "away_team": "Other Away",
                "home_team": "Other Home",
                "away": {"team_id": "1"},
                "home": {"team_id": "2"},
            },
        ],
    }
    monkeypatch.setattr(
        schedule.frozen,
        "load_with_diagnostics",
        lambda target_date: (
            [],
            {
                "games": 0,
                "identity_ready": False,
                "espn_matches": 0,
            },
        ),
    )
    monkeypatch.setattr(schedule, "_load_v2_snapshot", lambda: snapshot)

    _clear_v6_cache()
    games, diag = schedule.load_with_diagnostics("2026-09-10")
    _clear_v6_cache()

    assert len(games) == 1
    game = games[0]
    assert game["game_id"] == "401858213"
    assert game["identity_key"] == "espn:401858213"
    assert game["espn_event_id"] == "401858213"
    assert game["away_espn_team_id"] == "50"
    assert game["home_espn_team_id"] == "2390"
    assert game["away_team"] == "Florida A&M"
    assert game["home_team"] == "Miami"
    assert game["venue"] == "Hard Rock Stadium"
    assert game["broadcast"] == "ACC Network"
    assert game["identity_verified"] is True
    assert game["date_matches_query"] is True
    assert game["schedule_v6_runtime_snapshot_v2_seeded"] is True

    assert diag["games"] == 1
    assert diag["identity_ready"] is True
    assert diag["espn_matches"] == 1
    assert diag["runtime_snapshot_v2_seeded_games"] == 1
    assert diag["runtime_snapshot_v2_seed_fallback_active"] is True
    assert diag["official_ids_before_v2"] == 0
    assert diag["official_ids_after_v2"] == 1
    assert diag["fuzzy_matching"] is False
    assert diag["synthetic_ids"] is False


def test_v6_does_not_supplement_nonempty_frozen_v5_slate(monkeypatch):
    base_game = {
        "game_id": "ncaa-1",
        "identity_key": "ncaa:ncaa-1",
        "identity_fingerprint": "ncaa-1",
        "game_date": "2026-09-10",
        "away_team": "Base Away",
        "away_team_slug": "base-away",
        "home_team": "Base Home",
        "home_team_slug": "base-home",
        "identity_verified": True,
        "date_matches_query": True,
        "espn_event_id": "base-event",
    }
    snapshot = {
        "version": 2,
        "games": [
            {
                "event_id": "base-event",
                "game_date": "2026-09-10",
                "away_team": "Base Away",
                "home_team": "Base Home",
                "away": {"team_id": "10"},
                "home": {"team_id": "20"},
            },
            {
                "event_id": "snapshot-only-event",
                "game_date": "2026-09-10",
                "away_team": "Snapshot Away",
                "home_team": "Snapshot Home",
                "away": {"team_id": "30"},
                "home": {"team_id": "40"},
            },
        ],
    }
    monkeypatch.setattr(
        schedule.frozen,
        "load_with_diagnostics",
        lambda target_date: (
            [base_game],
            {
                "games": 1,
                "identity_ready": True,
                "espn_matches": 1,
            },
        ),
    )
    monkeypatch.setattr(schedule, "_load_v2_snapshot", lambda: snapshot)

    _clear_v6_cache()
    games, diag = schedule.load_with_diagnostics("2026-09-10")
    _clear_v6_cache()

    assert len(games) == 1
    assert games[0]["game_id"] == "ncaa-1"
    assert games[0]["espn_event_id"] == "base-event"
    assert games[0].get("schedule_v6_runtime_snapshot_v2_seeded") is not True
    assert diag["runtime_snapshot_v2_seeded_games"] == 0
    assert diag["runtime_snapshot_v2_seed_fallback_active"] is False

