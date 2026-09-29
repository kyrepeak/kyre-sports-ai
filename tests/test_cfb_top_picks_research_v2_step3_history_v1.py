from __future__ import annotations

import cfb_top_picks_history_router_v1 as history


def _row(**overrides):
    row = {
        "event_id": "401234567",
        "away": "Virginia",
        "home": "Florida State",
        "away_team_id": "258",
        "home_team_id": "52",
        "market": "OVER/UNDER",
        "pick": "Over 51.5",
    }
    row.update(overrides)
    return row


def _game():
    return {
        "espn_event_id": "401234567",
        "game_id": "401234567",
        "game_date": "2026-10-03",
        "kickoff_iso": "2026-10-03T20:00:00Z",
        "away_team": "Virginia",
        "home_team": "Florida State",
        "away_espn_team_id": "258",
        "home_espn_team_id": "52",
    }


def _espn(meetings=1):
    return {
        "head_to_head": {
            "ready": meetings > 0,
            "meetings": meetings,
            "sample": (
                [{
                    "event_id": "401111111",
                    "date": "2025-09-01T00:00:00Z",
                    "points_for": 24,
                    "points_against": 31,
                    "combined_total": 55,
                }]
                if meetings
                else []
            ),
        },
        "diagnostics": {
            "away_attempts": [{"http": 200, "bytes": 1000, "error": ""}],
            "home_attempts": [{"http": 200, "bytes": 1000, "error": ""}],
        },
    }


def _wins(meetings=4):
    if not meetings:
        return {}
    return {
        "ready": True,
        "source": "Winsipedia",
        "source_url": "https://www.winsipedia.com/games/virginia/vs/florida-state",
        "meetings": meetings,
        "away_wins": 1,
        "home_wins": 3,
        "ties": 0,
        "avg_combined_total": 54.75,
        "sample": [
            {"date": "2025-09-01", "away_points": 24, "home_points": 31, "combined_total": 55},
            {"date": "2019-09-14", "away_points": 31, "home_points": 24, "combined_total": 55},
            {"date": "2014-11-08", "away_points": 20, "home_points": 34, "combined_total": 54},
            {"date": "2010-10-02", "away_points": 14, "home_points": 41, "combined_total": 55},
        ],
    }


def test_winsipedia_recovers_history_when_espn_recent_lane_misses(monkeypatch):
    monkeypatch.setattr(history.espn_history, "build_history_engine", lambda *a, **k: _espn(0))
    monkeypatch.setattr(history.recovery, "_fetch_winsipedia_games", lambda *a, **k: _wins())
    out = history.resolve_matchup_history(_row(), _game())
    assert out["status"] == history.VERIFIED_HISTORY
    assert out["meetings"] == 4
    assert "Winsipedia" in out["sources_verified"]
    assert out["source_count_attempted"] == 2
    assert out["no_history_claim_allowed"] is False


def test_espn_history_survives_external_provider_miss(monkeypatch):
    monkeypatch.setattr(history.espn_history, "build_history_engine", lambda *a, **k: _espn(1))
    monkeypatch.setattr(history.recovery, "_fetch_winsipedia_games", lambda *a, **k: {})
    out = history.resolve_matchup_history(_row(), _game())
    assert out["status"] == history.VERIFIED_HISTORY
    assert out["meetings"] == 1
    assert "ESPN" in out["sources_verified"]
    assert out["source_count_attempted"] == 2


def test_provider_miss_never_becomes_false_no_history(monkeypatch):
    monkeypatch.setattr(history.espn_history, "build_history_engine", lambda *a, **k: {
        "head_to_head": {},
        "diagnostics": {
            "away_attempts": [{"http": None, "bytes": 0, "error": "timeout"}],
            "home_attempts": [{"http": None, "bytes": 0, "error": "timeout"}],
        },
    })
    monkeypatch.setattr(history.recovery, "_fetch_winsipedia_games", lambda *a, **k: {})
    out = history.resolve_matchup_history(_row(), _game())
    assert out["status"] == history.SOURCE_CONFLICT_REVIEW
    assert out["no_history_claim_allowed"] is False
    assert out["sources_exhausted"] is False


def test_explicit_two_source_exhaustion_can_verify_no_history(monkeypatch):
    monkeypatch.setattr(history.espn_history, "build_history_engine", lambda *a, **k: _espn(0))
    monkeypatch.setattr(
        history.recovery,
        "_fetch_winsipedia_games",
        lambda *a, **k: {"ready": False, "source_status": "NO_HISTORY"},
    )
    out = history.resolve_matchup_history(_row(), _game())
    assert out["status"] == history.VERIFIED_NO_HISTORY
    assert out["no_history_claim_allowed"] is True
    assert out["sources_exhausted"] is True


def test_over_history_context_tracks_line_hits_without_changing_projection(monkeypatch):
    monkeypatch.setattr(history.espn_history, "build_history_engine", lambda *a, **k: _espn(1))
    monkeypatch.setattr(history.recovery, "_fetch_winsipedia_games", lambda *a, **k: _wins())
    out = history.resolve_matchup_history(_row(), _game())
    context = out["line_hit_context"]
    assert context["line"] == 51.5
    assert context["sample_games"] == 4
    assert context["hits"] == 4
    assert out["projection_weight"] == 0.0
    assert out["selection_weight"] == 0.0
    assert out["ranking_weight"] == 0.0
    assert out["sportsbook_projection_weight"] == 0.0
    assert out["api2_used"] is False


def test_alias_resolution_is_recorded_for_both_teams(monkeypatch):
    monkeypatch.setattr(history.espn_history, "build_history_engine", lambda *a, **k: _espn(1))
    monkeypatch.setattr(history.recovery, "_fetch_winsipedia_games", lambda *a, **k: _wins())
    out = history.resolve_matchup_history(_row(), _game())
    aliases = out["canonical_aliases"]
    assert aliases["away"]["espn_team_id"] == "258"
    assert aliases["home"]["espn_team_id"] == "52"
    assert aliases["away"]["winsipedia_slug"] == "virginia"
    assert aliases["home"]["winsipedia_slug"] == "florida-state"
