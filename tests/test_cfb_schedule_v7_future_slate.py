"""Regression tests for additive Schedule V7 future-slate recovery."""
from __future__ import annotations

from pathlib import Path

import cfb_schedule_v7_future_slate as schedule


def _official_row(
    event_id: str,
    *,
    day: str = "2026-09-11",
    away: str = "Norfolk State",
    home: str = "Virginia",
    away_id: str = "2450",
    home_id: str = "258",
    venue: str = "Scott Stadium",
    broadcast: str = "ACCNX",
) -> dict:
    return {
        "event_id": event_id,
        "game_date": day,
        "away_team": away,
        "home_team": home,
        "away_team_id": away_id,
        "home_team_id": home_id,
        "venue": venue,
        "broadcast": broadcast,
        "status": "Scheduled",
        "_official_snapshot_kind": "market_identity_v1",
    }


def _diag_payload() -> dict:
    return {
        "games": 0,
        "identity_ready": False,
        "espn_matches": 0,
        "venue_missing": 0,
        "broadcast_missing": 0,
    }


def _clear_cache() -> None:
    for fn in (schedule.load_with_diagnostics, schedule.games_for_date):
        try:
            fn.clear()
        except Exception:
            pass


def _stub_diag_snapshots(monkeypatch) -> None:
    monkeypatch.setattr(
        schedule,
        "_load_market_snapshot",
        lambda: {"games": [], "_future_slate_snapshot_source": "test-market"},
    )
    monkeypatch.setattr(
        schedule.frozen,
        "_load_v2_snapshot",
        lambda: {"version": 2, "games": [], "_runtime_snapshot_source": "test-runtime"},
    )


def test_v7_terminal_st_alias_is_deterministic_not_fuzzy():
    assert schedule._canonical_team("Norfolk St.") == "norfolk state"
    assert schedule._canonical_team("Norfolk State") == "norfolk state"
    assert schedule._canonical_team("St. Thomas") == "st thomas"


def test_v7_recovers_norfolk_state_official_identity_and_metadata(monkeypatch):
    base = {
        "game_id": "ncaa-old",
        "identity_key": "ncaa:ncaa-old",
        "identity_fingerprint": "ncaa-old",
        "game_date": "2026-09-11",
        "away_team": "Norfolk St.",
        "home_team": "Virginia",
        "venue": "Venue unavailable",
        "broadcast": "Broadcast unavailable",
        "status": "Scheduled",
        "identity_verified": True,
        "date_matches_query": True,
    }
    official = [_official_row("401858220")]

    monkeypatch.setattr(
        schedule.frozen,
        "load_with_diagnostics",
        lambda target_date: ([base], {**_diag_payload(), "games": 1}),
    )
    monkeypatch.setattr(schedule, "_official_rows_for_date", lambda day: official)
    _stub_diag_snapshots(monkeypatch)

    _clear_cache()
    games, diag = schedule.load_with_diagnostics("2026-09-11")
    _clear_cache()

    assert len(games) == 1
    game = games[0]
    assert game["espn_event_id"] == "401858220"
    assert game["game_id"] == "401858220"
    assert game["identity_key"] == "espn:401858220"
    assert game["away_espn_team_id"] == "2450"
    assert game["home_espn_team_id"] == "258"
    assert game["venue"] == "Scott Stadium"
    assert game["broadcast"] == "ACCNX"
    assert game["schedule_v7_future_slate_enriched"] is True

    assert diag["future_slate_identity_recovered"] == 1
    assert diag["future_slate_alias_recovered"] == 1
    assert diag["future_slate_supplemented_games"] == 0
    assert diag["official_ids_before_v7"] == 0
    assert diag["official_ids_after_v7"] == 1
    assert diag["fuzzy_matching"] is False
    assert diag["synthetic_ids"] is False
    assert diag["sportsbook_projection_weight"] == 0.0


def test_v7_alias_collision_fails_closed():
    game = {
        "game_date": "2026-09-11",
        "away_team": "Norfolk St.",
        "home_team": "Virginia",
    }
    rows = [
        _official_row("401858220"),
        _official_row("401858999"),
    ]

    match, method = schedule._unique_official_match(game, rows)

    assert match == {}
    assert method == "collision"


def test_v7_supplements_partial_nonempty_slate(monkeypatch):
    base = {
        "game_id": "401856678",
        "identity_key": "espn:401856678",
        "identity_fingerprint": "espn:401856678",
        "game_date": "2026-09-11",
        "away_team": "Missouri",
        "home_team": "Kansas",
        "espn_event_id": "401856678",
        "away_espn_team_id": "142",
        "home_espn_team_id": "2305",
        "venue": "David Booth Kansas Memorial Stadium",
        "broadcast": "FOX",
        "identity_verified": True,
        "date_matches_query": True,
    }
    rows = [
        _official_row(
            "401856678",
            away="Missouri",
            home="Kansas",
            away_id="142",
            home_id="2305",
            venue="David Booth Kansas Memorial Stadium",
            broadcast="FOX",
        ),
        _official_row("401858220"),
    ]

    monkeypatch.setattr(
        schedule.frozen,
        "load_with_diagnostics",
        lambda target_date: ([base], {**_diag_payload(), "games": 1, "espn_matches": 1}),
    )
    monkeypatch.setattr(schedule, "_official_rows_for_date", lambda day: rows)
    _stub_diag_snapshots(monkeypatch)

    _clear_cache()
    games, diag = schedule.load_with_diagnostics("2026-09-11")
    _clear_cache()

    assert {game["espn_event_id"] for game in games} == {"401856678", "401858220"}
    assert diag["future_slate_supplemented_games"] == 1
    assert diag["games"] == 2
    assert diag["identity_ready"] is True


def test_v7_can_seed_future_market_horizon_when_base_is_empty(monkeypatch):
    day = "2026-09-18"
    rows = [
        _official_row(
            "401999001",
            day=day,
            away="Future Away",
            home="Future Home",
            away_id="9001",
            home_id="9002",
            venue="Future Stadium",
            broadcast="ESPN",
        )
    ]

    monkeypatch.setattr(
        schedule.frozen,
        "load_with_diagnostics",
        lambda target_date: ([], _diag_payload()),
    )
    monkeypatch.setattr(schedule, "_official_rows_for_date", lambda requested_day: rows)
    _stub_diag_snapshots(monkeypatch)

    _clear_cache()
    games, diag = schedule.load_with_diagnostics(day)
    _clear_cache()

    assert len(games) == 1
    assert games[0]["espn_event_id"] == "401999001"
    assert games[0]["schedule_v7_future_slate_seeded"] is True
    assert games[0]["venue"] == "Future Stadium"
    assert games[0]["broadcast"] == "ESPN"
    assert diag["future_slate_supplemented_games"] == 1
    assert diag["official_ids_after_v7"] == 1


def test_v30_and_router_v70_are_the_only_new_active_layers():
    import cfb_over_under_clean_page_v30 as page
    import cfb_schedule_v7_future_slate as schedule_v7
    import streamlit_memory_lazy_router_v70 as router

    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v29"
    assert page.ACTIVE_SCHEDULE == "cfb_schedule_v7_future_slate"
    assert page._RENDER_V30.__globals__["schedule_v6"] is schedule_v7
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v69"
    assert "V70" in router.MODEL_VERSION

    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v70 import render_app" in app_source
    assert "STREAMLIT_MAIN_V70_CFB_OU_FUTURE_SLATE_COVERAGE_2026-09-10" in app_source
