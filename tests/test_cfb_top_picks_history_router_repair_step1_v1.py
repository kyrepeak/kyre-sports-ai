from __future__ import annotations

import cfb_top_picks_history_router_v1 as history


def _row():
    return {
        "event_id": "401858253",
        "away": "Virginia",
        "home": "Florida St.",
        "away_team_id": "258",
        "home_team_id": "52",
        "market": "OVER/UNDER",
        "pick": "Over 51.5",
    }


def _game():
    return {
        "espn_event_id": "401858253",
        "game_id": "401858253",
        "game_date": "2026-10-03",
        "away_team": "Virginia",
        "home_team": "Florida St.",
        "away_espn_team_id": "258",
        "home_espn_team_id": "52",
    }


def _healthy_espn_miss():
    return {
        "head_to_head": {"meetings": 0, "sample": []},
        "diagnostics": {
            "away_attempts": [{"http": 200, "bytes": 900, "error": ""}],
            "home_attempts": [{"http": 200, "bytes": 900, "error": ""}],
        },
    }


def _verified_series():
    return {
        "ready": True,
        "source": "Winsipedia",
        "source_url": "https://www.winsipedia.com/games/florida-state/vs/virginia",
        "meetings": 4,
        "away_wins": 2,
        "home_wins": 2,
        "ties": 0,
        "avg_combined_total": 56.5,
        "sample": [
            {"date": "2025-09-26", "away_points": 46, "home_points": 38, "combined_total": 84},
            {"date": "2019-09-14", "away_points": 31, "home_points": 24, "combined_total": 55},
            {"date": "2014-11-08", "away_points": 20, "home_points": 34, "combined_total": 54},
            {"date": "2011-11-19", "away_points": 14, "home_points": 13, "combined_total": 27},
        ],
    }


def test_florida_st_display_alias_is_canonicalized_before_winsipedia(monkeypatch):
    calls = []

    monkeypatch.setattr(
        history.espn_history,
        "build_history_engine",
        lambda *a, **k: _healthy_espn_miss(),
    )

    def fake_winsipedia(away, home):
        calls.append((away, home))
        return _verified_series()

    monkeypatch.setattr(history.recovery, "_fetch_winsipedia_games", fake_winsipedia)

    out = history.resolve_matchup_history(_row(), _game())

    assert calls == [("Virginia", "Florida State")]
    assert out["status"] == history.VERIFIED_HISTORY
    assert out["history_ready"] is True
    assert out["meetings"] == 4
    assert "Winsipedia" in out["sources_verified"]
    assert out["canonical_aliases"]["home"]["canonical_name"] == "Florida St."
    assert out["canonical_aliases"]["home"]["winsipedia_lookup_name"] == "Florida State"
    assert out["canonical_aliases"]["home"]["winsipedia_slug"] == "florida-state"
    wins_attempt = next(x for x in out["sources_attempted"] if x["source"] == "Winsipedia")
    assert wins_attempt["lookup_names"]["home"] == "Florida State"


def test_generic_trailing_st_display_abbreviation_expands_only_for_history_lookup():
    assert history._winsipedia_lookup_name("Arizona St.", "9") == "Arizona State"
    assert history._winsipedia_lookup_name("Florida St", "52") == "Florida State"
    assert history._winsipedia_lookup_name("Virginia", "258") == "Virginia"


def test_history_alias_repair_cannot_change_projection_ranking_or_selection(monkeypatch):
    monkeypatch.setattr(
        history.espn_history,
        "build_history_engine",
        lambda *a, **k: _healthy_espn_miss(),
    )
    monkeypatch.setattr(
        history.recovery,
        "_fetch_winsipedia_games",
        lambda *a, **k: _verified_series(),
    )
    out = history.resolve_matchup_history(_row(), _game())
    assert out["projection_weight"] == 0.0
    assert out["selection_weight"] == 0.0
    assert out["ranking_weight"] == 0.0
    assert out["sportsbook_projection_weight"] == 0.0
    assert out["api2_used"] is False
