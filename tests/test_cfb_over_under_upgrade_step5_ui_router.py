"""Regression checks for CFB O/U Upgrade Step 5 UI and Router V45."""
from __future__ import annotations

import types

import cfb_over_under_matchup_ui_v5 as ui
import streamlit_memory_lazy_router_v45 as router


def _game():
    return {
        "game_date": "2026-09-10",
        "away_team": "Florida A&M",
        "home_team": "Miami (FL)",
    }


def _away():
    return {"team": "Florida A&M"}


def _home():
    return {"team": "Miami (FL)"}


def _engine():
    return {
        "model_ready": True,
        "away_offense": {
            "offense_team": "Florida A&M",
            "defense_team": "Miami (FL)",
            "offense_division": "FCS",
            "defense_division": "FBS",
            "label": "EXPLOSIVE EDGE",
            "points_adjustment": 0.25,
            "coverage": 0.60,
            "sample_factor": 0.20,
            "pass": {
                "ready": True,
                "signal": 0.4,
                "offense_yards_per_attempt": 6.4,
                "defense_yards_per_attempt_allowed": 5.3,
                "offense_yards_per_completion": 13.0,
                "defense_yards_per_completion_allowed": 10.0,
            },
            "rush": {"ready": False, "signal": 0.0},
        },
        "home_offense": {
            "offense_team": "Miami (FL)",
            "defense_team": "Florida A&M",
            "offense_division": "FBS",
            "defense_division": "FCS",
            "label": "STRONG EXPLOSIVE EDGE",
            "points_adjustment": 0.30,
            "coverage": 1.0,
            "sample_factor": 0.20,
            "pass": {
                "ready": True,
                "signal": 0.8,
                "offense_yards_per_attempt": 12.2,
                "defense_yards_per_attempt_allowed": 8.3,
                "offense_yards_per_completion": 14.3,
                "defense_yards_per_completion_allowed": 13.3,
            },
            "rush": {
                "ready": True,
                "signal": -0.1,
                "offense_yards_per_rush": 3.78,
                "defense_yards_per_rush_allowed": 3.93,
            },
        },
    }


def test_hero_preserves_step4_and_adds_explosive_panel(monkeypatch):
    monkeypatch.setattr(ui, "_FROZEN_STEP4_HERO", lambda *a, **k: "<STEP4/>")
    monkeypatch.setattr(
        ui.explosive_engine,
        "build_explosive_engine",
        lambda *a, **k: _engine(),
    )

    html = ui._hero_v5(_game(), _away(), _home())

    assert "<STEP4/>" in html
    assert "UPGRADE STEP 5" in html
    assert "Pass chunk efficiency" in html
    assert "Rush chunk efficiency" in html
    assert "20+ yard pass-play" in html


def test_explosive_panel_fails_closed(monkeypatch):
    monkeypatch.setattr(
        ui.explosive_engine,
        "build_explosive_engine",
        lambda *a, **k: {
            "model_ready": False,
            "reason": "missing explosive proxy evidence",
        },
    )
    html = ui._explosive_panel(_game(), _away(), _home())
    assert "EXPLOSIVE ADJUSTMENT GATED" in html
    assert "missing explosive proxy evidence" in html


def test_model_card_reports_step4_to_step5_transition():
    output = {
        "ready": True,
        "upgrade_step5_applied": True,
        "step5_base_projected_total": 50.0,
        "projected_total": 50.6,
        "projected_away_points": 20.2,
        "projected_home_points": 30.4,
        "analysis_line": 50.5,
        "over_probability": 0.51,
        "under_probability": 0.49,
        "push_probability": 0.0,
        "model_lean": "OVER",
        "explosive_engine_coverage": 0.8,
        "reliability": 0.7,
        "components": {
            "step5_away_explosive_adjustment": 0.2,
            "step5_home_explosive_adjustment": 0.4,
            "step5_total_explosive_adjustment": 0.6,
        },
    }
    html = ui._model_card_v5(_game(), _away(), _home(), output)
    assert "STEP 5 • EXPLOSIVE-ADJUSTED OVER/UNDER MODEL" in html
    assert "Step 4 50.0 → explosive adjusted 50.6" in html
    assert "Explosive coverage" in html


def test_render_wrapper_patches_v4_symbols_and_restores(monkeypatch):
    originals = {
        "hero": ui.frozen_v4._hero_v4,
        "slate": ui.frozen_v4.upgraded_slate,
        "model": ui.frozen_v4._model_card_v4,
        "components": ui.frozen_v4._components_panel_v4,
        "final": ui.frozen_v4._final_card_v4,
    }
    seen = {}

    monkeypatch.setattr(ui.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(ui.st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(ui, "_clear_stale_scan_state", lambda: None)

    def fake_render(*args, **kwargs):
        seen["hero"] = ui.frozen_v4._hero_v4
        seen["slate"] = ui.frozen_v4.upgraded_slate
        seen["model"] = ui.frozen_v4._model_card_v4
        seen["components"] = ui.frozen_v4._components_panel_v4
        seen["final"] = ui.frozen_v4._final_card_v4
        return "ok"

    monkeypatch.setattr(ui.frozen_v4, "render_over_under_hub", fake_render)

    result = ui.render_over_under_hub()

    assert result == "ok"
    assert seen["hero"] is ui._hero_v5
    assert seen["slate"] is ui.upgraded_slate
    assert seen["model"] is ui._model_card_v5
    assert seen["components"] is ui._components_panel_v5
    assert seen["final"] is ui._final_card_v5

    assert ui.frozen_v4._hero_v4 is originals["hero"]
    assert ui.frozen_v4.upgraded_slate is originals["slate"]
    assert ui.frozen_v4._model_card_v4 is originals["model"]
    assert ui.frozen_v4._components_panel_v4 is originals["components"]
    assert ui.frozen_v4._final_card_v4 is originals["final"]


def test_router_v45_only_advances_cfb_over_under(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football"},
    )

    def render_cfb_hub(market, section_header, status_info, team_logo, h):
        seen["market"] = market

    module = types.SimpleNamespace(render_cfb_hub=render_cfb_hub)

    def fake_import(name):
        seen["module"] = name
        return module

    monkeypatch.setattr(router.root, "_import", fake_import)
    router._render_nfl_or_cfb_v45("Over/Under")

    assert seen["module"] == "cfb_over_under_matchup_ui_v5"
    assert seen["market"] == "Over/Under"


def test_router_v45_delegates_other_routes(monkeypatch):
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
    router._render_nfl_or_cfb_v45("Moneyline")
    router._render_nfl_or_cfb_v45("Game Total")

    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    router._render_nfl_or_cfb_v45("Over/Under")

    assert seen == ["Moneyline", "Game Total", "Over/Under"]


def test_render_app_temporarily_patches_v44_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v44
    seen = {}

    def fake_render_app():
        seen["during"] = router.prior._render_nfl_or_cfb_v44

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)
    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v45
    assert router.prior._render_nfl_or_cfb_v44 is original
