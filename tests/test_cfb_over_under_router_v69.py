"""Regression tests for CFB O/U Router V69 plus additive V70 handoff."""
from __future__ import annotations

import inspect

import streamlit_memory_lazy_router_v69 as router


def test_router_v69_is_additive_over_v68():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v68"
    assert router.OVER_UNDER_MARKET == "Over/Under"
    assert router._FROZEN_RENDER_NFL_OR_CFB is router.prior._render_nfl_or_cfb_v68


def test_router_v69_routes_only_cfb_over_under_to_v29(monkeypatch):
    calls = []

    class Page:
        def render_cfb_hub(self, market, *args):
            calls.append(("v29", market))

    monkeypatch.setitem(router.st.session_state, "ks_sport_touch", router.CFB_SPORT_LABEL)
    monkeypatch.setattr(
        router.root,
        "_import",
        lambda name: Page() if name == "cfb_over_under_clean_page_v29" else None,
    )
    router._render_nfl_or_cfb_v69("Over/Under")
    assert calls == [("v29", "Over/Under")]


def test_router_v69_delegates_non_target_routes(monkeypatch):
    calls = []
    monkeypatch.setitem(router.st.session_state, "ks_sport_touch", router.CFB_SPORT_LABEL)
    monkeypatch.setattr(router, "_FROZEN_RENDER_NFL_OR_CFB", lambda market: calls.append(market))
    router._render_nfl_or_cfb_v69("Moneyline")
    assert calls == ["Moneyline"]


def test_router_v69_delegates_non_cfb_over_under_routes(monkeypatch):
    calls = []
    monkeypatch.setitem(router.st.session_state, "ks_sport_touch", "NFL")
    monkeypatch.setattr(router, "_FROZEN_RENDER_NFL_OR_CFB", lambda market: calls.append(market))
    router._render_nfl_or_cfb_v69("Over/Under")
    assert calls == ["Over/Under"]


def test_router_v69_contains_no_model_or_market_reimplementation():
    source = inspect.getsource(router)
    for token in (
        "analyze_game(",
        "attach_market_lines(",
        "build_market_intelligence(",
        "build_form_strength_engine(",
        "certify_result(",
    ):
        assert token not in source


def test_render_app_patches_v68_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v68
    seen = {}
    monkeypatch.setattr(
        router.prior,
        "render_app",
        lambda: seen.update({"during": router.prior._render_nfl_or_cfb_v68}),
    )
    router.render_app()
    assert seen["during"] is router._render_nfl_or_cfb_v69
    assert router.prior._render_nfl_or_cfb_v68 is original


def test_v70_future_slate_handoff_recovers_norfolk_state_without_fuzzy_matching():
    import cfb_over_under_clean_page_v30 as page_v30
    import cfb_schedule_v7_future_slate as schedule_v7
    import streamlit_memory_lazy_router_v70 as router_v70

    base = {
        "game_date": "2026-09-11",
        "away_team": "Norfolk St.",
        "home_team": "Virginia",
    }
    official = [
        {
            "event_id": "401858220",
            "game_date": "2026-09-11",
            "away_team": "Norfolk State",
            "home_team": "Virginia",
            "away_team_id": "2450",
            "home_team_id": "258",
            "venue": "Scott Stadium",
            "broadcast": "ACCNX",
            "status": "Scheduled",
            "_official_snapshot_kind": "market_identity_v1",
        }
    ]

    match, method = schedule_v7._unique_official_match(base, official)

    assert method == "deterministic_alias"
    assert match["event_id"] == "401858220"
    assert schedule_v7._canonical_team("Norfolk St.") == "norfolk state"
    assert schedule_v7._canonical_team("Norfolk State") == "norfolk state"
    assert schedule_v7.MARKET_PROJECTION_WEIGHT == 0.0
    assert page_v30.FROZEN_PAGE == "cfb_over_under_clean_page_v29"
    assert page_v30.ACTIVE_SCHEDULE == "cfb_schedule_v7_future_slate"
    assert page_v30._RENDER_V30.__globals__["schedule_v6"] is schedule_v7
    assert router_v70.FROZEN_ROUTER == "streamlit_memory_lazy_router_v69"


def test_v7_supplements_partial_slate_and_preserves_official_metadata(monkeypatch):
    import cfb_schedule_v7_future_slate as schedule_v7

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
    official = [
        {
            "event_id": "401856678",
            "game_date": "2026-09-11",
            "away_team": "Missouri",
            "home_team": "Kansas",
            "away_team_id": "142",
            "home_team_id": "2305",
            "venue": "David Booth Kansas Memorial Stadium",
            "broadcast": "FOX",
            "status": "Scheduled",
            "_official_snapshot_kind": "market_identity_v1",
        },
        {
            "event_id": "401858220",
            "game_date": "2026-09-11",
            "away_team": "Norfolk State",
            "home_team": "Virginia",
            "away_team_id": "2450",
            "home_team_id": "258",
            "venue": "Scott Stadium",
            "broadcast": "ACCNX",
            "status": "Scheduled",
            "_official_snapshot_kind": "market_identity_v1",
        },
    ]

    monkeypatch.setattr(
        schedule_v7.frozen,
        "load_with_diagnostics",
        lambda target_date: (
            [base],
            {
                "games": 1,
                "identity_ready": True,
                "espn_matches": 1,
                "venue_missing": 0,
                "broadcast_missing": 0,
            },
        ),
    )
    monkeypatch.setattr(schedule_v7, "_official_rows_for_date", lambda day: official)
    monkeypatch.setattr(
        schedule_v7,
        "_load_market_snapshot",
        lambda: {"games": [], "_future_slate_snapshot_source": "test-market"},
    )
    monkeypatch.setattr(
        schedule_v7.frozen,
        "_load_v2_snapshot",
        lambda: {"version": 2, "games": [], "_runtime_snapshot_source": "test-runtime"},
    )

    for fn in (schedule_v7.load_with_diagnostics, schedule_v7.games_for_date):
        try:
            fn.clear()
        except Exception:
            pass
    games, diag = schedule_v7.load_with_diagnostics("2026-09-11")
    for fn in (schedule_v7.load_with_diagnostics, schedule_v7.games_for_date):
        try:
            fn.clear()
        except Exception:
            pass

    assert {game["espn_event_id"] for game in games} == {"401856678", "401858220"}
    norfolk = next(game for game in games if game["espn_event_id"] == "401858220")
    assert norfolk["venue"] == "Scott Stadium"
    assert norfolk["broadcast"] == "ACCNX"
    assert diag["future_slate_supplemented_games"] == 1
    assert diag["fuzzy_matching"] is False
    assert diag["synthetic_ids"] is False
    assert diag["sportsbook_projection_weight"] == 0.0
