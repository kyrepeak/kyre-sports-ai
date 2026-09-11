"""Regression tests for CFB Over/Under performance Step 4."""
from __future__ import annotations

from pathlib import Path
import types

import cfb_over_under_analysis_prewarm_v1 as prewarm
import cfb_over_under_clean_page_v34 as page
import cfb_over_under_performance_profiler_v1 as profiler
import streamlit_memory_lazy_router_v75 as router


def _game() -> dict:
    return {
        "game_id": "401858220",
        "espn_event_id": "401858220",
        "identity_key": "espn:401858220",
        "game_date": "2026-09-11",
        "away_team": "Norfolk State",
        "home_team": "Virginia",
        "away_espn_team_id": "2450",
        "home_espn_team_id": "258",
    }


def test_prewarm_is_cache_only_and_projection_neutral(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        prewarm,
        "_warm_runtime_foundation",
        lambda game, day: {
            "game": dict(game),
            "away": {"team": "A", "division_context": "FBS"},
            "home": {"team": "B", "division_context": "FBS"},
            "diag": {},
        },
    )
    monkeypatch.setattr(
        prewarm,
        "_warm_matchup_tables",
        lambda foundation: calls.append("step3") or {"warmed": True},
    )
    monkeypatch.setattr(
        prewarm,
        "_warm_pair",
        lambda loader: calls.append(getattr(loader, "__name__", "loader")) or {},
    )
    monkeypatch.setattr(
        prewarm,
        "_warm_environment_history",
        lambda game, day: calls.append("env_history") or {},
    )
    monkeypatch.setattr(
        prewarm,
        "_warm_h2h_context",
        lambda game: calls.append("h2h") or {},
    )

    result = prewarm.warm_selected_game(_game(), "2026-09-11")

    assert result["status"] == "GREEN"
    assert result["projection_weight"] == 0.0
    assert result["may_modify_projection"] is False
    assert result["sportsbook_input_used"] is False
    assert result["fuzzy_matching"] is False
    assert result["synthetic_ids"] is False
    assert "step3" in calls
    assert "env_history" in calls
    assert "h2h" in calls

    source = Path("cfb_over_under_analysis_prewarm_v1.py").read_text(encoding="utf-8")
    assert "project_matchup(" not in source
    assert "apply_to_raw(" not in source
    assert "rank_slate(" not in source


def test_schedule_proxy_tracks_only_current_run_and_selected_index(monkeypatch):
    games = [_game(), {**_game(), "espn_event_id": "2", "game_id": "2", "away_team": "X"}]
    fake_schedule = types.SimpleNamespace(
        load_with_diagnostics=lambda day: (games, {"version": "fake"})
    )
    monkeypatch.setattr(page, "_BASE_SCHEDULE", fake_schedule)
    monkeypatch.setattr(page.st, "session_state", {"cfb_ou_v18_matchup_2026-09-11": 1})

    returned, _ = page._SCHEDULE_PROXY.load_with_diagnostics("2026-09-11")
    selected = page._selected_game_from_context("2026-09-11")

    assert returned == games
    assert selected["espn_event_id"] == "2"
    assert page._selected_game_from_context("2026-09-12") == {}


def test_market_proxy_overlaps_prewarm_without_changing_market_result(monkeypatch):
    expected = ({"games": [{"game_id": "401858220"}]}, {"status": "GREEN"})
    fake_market = types.SimpleNamespace(
        load_odds_for_date=lambda *args, **kwargs: expected,
    )
    monkeypatch.setattr(page, "_BASE_MARKET", fake_market)
    monkeypatch.setattr(page.st, "session_state", {})
    page._SCHEDULE_CONTEXT.set({"day": "2026-09-11", "games": [_game()]})
    monkeypatch.setattr(
        page.prewarm,
        "warm_selected_game",
        lambda game, day: {
            "version": "test",
            "status": "GREEN",
            "elapsed_ms": 1.0,
            "projection_weight": 0.0,
            "may_modify_projection": False,
        },
    )

    trace = profiler.PerfTrace()
    token = profiler.set_active_trace(trace)
    try:
        result = page._MARKET_PROXY.load_odds_for_date("2026-09-11", "FanDuel")
    finally:
        profiler.reset_active_trace(token)

    assert result == expected
    assert page.st.session_state["cfb_ou_prewarm_v1_last"]["status"] == "GREEN"
    labels = [label for label, _ in trace.events]
    assert "analysis.prewarm.parallel" in labels
    assert "analysis.prewarm.wait_after_market" in labels


def test_v34_marker_preserves_browser_and_frozen_contract_phrases():
    marker = page._V34_MARKER
    assert "CFB O/U • CLEAN PAGE V34 ACTIVE" in marker
    assert "CFB O/U • CLEAN PAGE V30 ACTIVE" in marker
    assert "FUTURE SLATE COVERAGE ACTIVE" in marker
    assert "OFFICIAL ESPN IDENTITY RECOVERY" in marker
    assert "NO FUZZY MATCHING" in marker
    assert "NO SYNTHETIC IDS" in marker
    assert "FRESHNESS FIREWALL ACTIVE" in marker
    assert "0.0% PROJECTION INFLUENCE" in marker
    assert "FROZEN PROJECTION MATH PRESERVED" in marker
    assert "READABLE STEPS 4-12 ACTIVE" in marker


def test_router_v75_targets_only_v34_for_active_cfb_over_under(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football", "ks_cfb_market_touch": "Over/Under"},
    )
    module = types.SimpleNamespace(
        render_cfb_hub=lambda market, *args: seen.update({"market": market})
    )
    monkeypatch.setattr(
        router.root,
        "_import",
        lambda name: (seen.update({"module": name}) or module),
    )

    router._render_cfb_ou_direct("Over/Under")

    assert router.ACTIVE_PAGE == "cfb_over_under_clean_page_v34"
    assert seen == {
        "module": "cfb_over_under_clean_page_v34",
        "market": "Over/Under",
    }


def test_app_advances_to_v75_and_retains_v74_guard():
    text = Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v74 import render_app as _frozen_v74_render_app" in text
    assert "from streamlit_memory_lazy_router_v75 import render_app" in text
    assert (
        'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V75_CFB_OU_PARALLEL_PREWARM_2026-09-11"'
        in text
    )
    assert "frozen V14 projection math" in text
    assert "0.0% sportsbook projection influence" in text
