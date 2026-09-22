"""Regression checks for CFB O/U post-12 recovery slate/UI/router."""
from __future__ import annotations

import types

import cfb_over_under_matchup_ui_v13_data_recovery as ui
import cfb_over_under_slate_v12_data_recovery as slate
import streamlit_memory_lazy_router_v53 as router


def test_ui_all_time_series_panel_is_not_blank():
    html = ui._all_time_h2h({
        "ready": True,
        "source": "Winsipedia",
        "meetings": 12,
        "away_wins": 1,
        "home_wins": 11,
        "avg_combined_total": 55.3,
        "latest": {
            "date": "2024-09-07",
            "away_points": 9,
            "home_points": 56,
            "combined_total": 65,
        },
    })
    assert "ALL-TIME SERIES" in html
    assert "12" in html
    assert "2024-09-07" in html
    assert "9–56" in html
    assert "projection weight 0%" in html


def test_form_limited_panel_still_shows_verified_counts(monkeypatch):
    monkeypatch.setattr(
        ui.form_engine,
        "build_form_strength_engine",
        lambda *a, **k: {
            "model_ready": False,
            "reason": "home current-season sample below 2 games",
            "away_form": {"games": 2, "opponent_record_coverage": 1.0},
            "home_form": {"games": 1, "opponent_record_coverage": 1.0},
        },
    )
    html = ui._form_panel({}, {}, {}, {})
    assert "FORM LIMITED" in html
    assert "2" in html
    assert "1" in html
    assert "100.0%" in html
    assert "cannot force an adjustment" in html


def test_router_v53_only_advances_cfb_ou(monkeypatch):
    seen = {}
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "College Football"})
    module = types.SimpleNamespace(
        render_cfb_hub=lambda market,*args: seen.update({"market": market})
    )
    monkeypatch.setattr(
        router.root,
        "_import",
        lambda name: (seen.update({"module": name}) or module),
    )
    router._render_nfl_or_cfb_v53("Over/Under")
    assert seen["module"] == "cfb_over_under_matchup_ui_v13_data_recovery"
    assert seen["market"] == "Over/Under"


def test_router_v53_delegates_other_routes(monkeypatch):
    seen = []
    monkeypatch.setattr(router, "_FROZEN_RENDER_NFL_OR_CFB", lambda m: seen.append(m))
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "College Football"})
    router._render_nfl_or_cfb_v53("Moneyline")
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    router._render_nfl_or_cfb_v53("Over/Under")
    assert seen == ["Moneyline", "Over/Under"]


def test_render_app_patches_v52_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v52
    seen = {}
    monkeypatch.setattr(
        router.prior,
        "render_app",
        lambda: seen.update({"during": router.prior._render_nfl_or_cfb_v52}),
    )
    router.render_app()
    assert seen["during"] is router._render_nfl_or_cfb_v53
    assert router.prior._render_nfl_or_cfb_v52 is original
