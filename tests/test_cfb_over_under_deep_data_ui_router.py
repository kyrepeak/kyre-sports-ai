"""UI/router regressions for CFB O/U deep-data reconciliation."""
from __future__ import annotations

import types

import cfb_over_under_matchup_ui_v14_deep_data as ui
import streamlit_memory_lazy_router_v54 as router


def _profiles():
    away = {
        "team": "Florida A&M",
        "conference": "SWAC",
        "division_context": "FCS",
        "record_text": "1-1",
        "conference_record_text": "0-0",
        "recent_form": "WL",
        "current_schedule_games_verified": 2,
        "head_coach": "Quinn Gray Sr.",
        "head_coach_source": "ESPN Core current-season head coach",
        "polls": {},
    }
    home = {
        "team": "Miami (FL)",
        "conference": "ACC",
        "division_context": "FBS",
        "record_text": "1-0",
        "conference_record_text": "1-0",
        "recent_form": "W",
        "current_schedule_games_verified": 1,
        "head_coach": "Mario Cristobal",
        "head_coach_source": "ESPN Core current-season head coach",
        "polls": {
            "ap": {"rank": 7},
            "coaches": {"rank": 7},
        },
    }
    return away, home


def test_current_data_panel_contains_correct_live_fields():
    away, home = _profiles()
    html = ui._current_data_panel({
        "venue": "Hard Rock Stadium",
        "venue_city": "Miami Gardens",
        "venue_state": "FL",
        "broadcast": "ACC Network",
        "status": "Scheduled",
        "espn_week": 2,
    }, away, home)
    for token in (
        "Hard Rock Stadium",
        "ACC Network",
        "Florida A&amp;M",
        "Miami (FL)",
        "1-1",
        "1-0",
        "Mario Cristobal",
        "Quinn Gray Sr.",
        "#7",
        "CURRENT RECORDS",
    ):
        assert token in html


def test_router_v54_only_advances_cfb_over_under(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football"},
    )
    module = types.SimpleNamespace(
        render_cfb_hub=lambda market,*args: seen.update({"market": market})
    )
    monkeypatch.setattr(
        router.root,
        "_import",
        lambda name: (seen.update({"module": name}) or module),
    )
    router._render_nfl_or_cfb_v54("Over/Under")
    assert seen["module"] == "cfb_over_under_matchup_ui_v14_deep_data"
    assert seen["market"] == "Over/Under"


def test_router_v54_delegates_other_routes(monkeypatch):
    seen = []
    monkeypatch.setattr(
        router,
        "_FROZEN_RENDER_NFL_OR_CFB",
        lambda market: seen.append(market),
    )
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football"},
    )
    router._render_nfl_or_cfb_v54("Moneyline")
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "NFL"},
    )
    router._render_nfl_or_cfb_v54("Over/Under")
    assert seen == ["Moneyline", "Over/Under"]


def test_render_app_patches_v53_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v53
    seen = {}
    monkeypatch.setattr(
        router.prior,
        "render_app",
        lambda: seen.update({"during": router.prior._render_nfl_or_cfb_v53}),
    )
    router.render_app()
    assert seen["during"] is router._render_nfl_or_cfb_v54
    assert router.prior._render_nfl_or_cfb_v53 is original
