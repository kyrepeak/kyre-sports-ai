"""Regression checks for CFB O/U Upgrade Step 7 UI and Router V47."""
from __future__ import annotations

import types

import cfb_over_under_matchup_ui_v7 as ui
import streamlit_memory_lazy_router_v47 as router


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


def _metrics(team, attempts, conversions, rate, apg):
    return {
        "team": team,
        "ready": True,
        "attempts": attempts,
        "conversions": conversions,
        "conversion_rate": rate,
        "attempts_per_game": apg,
    }


def _engine():
    return {
        "model_ready": True,
        "away_offense": {
            "offense_team": "Florida A&M",
            "defense_team": "Miami (FL)",
            "offense_division": "FCS",
            "defense_division": "FBS",
            "label": "DRIVE-SUPPRESSION",
            "points_adjustment": -0.30,
            "coverage": 1.0,
            "sample_factor": 0.50,
            "matchup_conversion_rate": 0.283,
            "expected_third_down_attempts_per_game": 15.0,
            "expected_third_down_conversions_per_game": 4.25,
            "offense": _metrics("Florida A&M", 30, 7, 7/30, 15.0),
            "defense": _metrics("Miami (FL)", 15, 5, 5/15, 15.0),
        },
        "home_offense": {
            "offense_team": "Miami (FL)",
            "defense_team": "Florida A&M",
            "offense_division": "FBS",
            "defense_division": "FCS",
            "label": "DRIVE-SUSTAIN EDGE",
            "points_adjustment": 0.15,
            "coverage": 1.0,
            "sample_factor": 11/30,
            "matchup_conversion_rate": 0.442,
            "expected_third_down_attempts_per_game": 10.25,
            "expected_third_down_conversions_per_game": 4.53,
            "offense": _metrics("Miami (FL)", 11, 8, 8/11, 11.0),
            "defense": _metrics("Florida A&M", 19, 3, 3/19, 9.5),
        },
    }


def test_hero_preserves_step6_and_adds_third_down_panel(monkeypatch):
    monkeypatch.setattr(ui, "_FROZEN_STEP6_HERO", lambda *a, **k: "<STEP6/>")
    monkeypatch.setattr(
        ui.third_down_engine,
        "build_third_down_engine",
        lambda *a, **k: _engine(),
    )

    html = ui._hero_v7(_game(), _away(), _home())

    assert "<STEP6/>" in html
    assert "UPGRADE STEP 7" in html
    assert "3rd-down offense" in html
    assert "Opponent 3rd-down defense" in html
    assert "blended 50/50" in html


def test_third_down_panel_fails_closed(monkeypatch):
    monkeypatch.setattr(
        ui.third_down_engine,
        "build_third_down_engine",
        lambda *a, **k: {
            "model_ready": False,
            "reason": "missing direct third-down row",
        },
    )
    html = ui._third_down_panel(_game(), _away(), _home())
    assert "THIRD-DOWN ADJUSTMENT GATED" in html
    assert "missing direct third-down row" in html


def test_model_card_reports_step6_to_step7_transition():
    output = {
        "ready": True,
        "upgrade_step7_applied": True,
        "step7_base_projected_total": 50.0,
        "projected_total": 49.8,
        "projected_away_points": 19.7,
        "projected_home_points": 30.1,
        "analysis_line": 50.5,
        "over_probability": 0.47,
        "under_probability": 0.53,
        "push_probability": 0.0,
        "model_lean": "UNDER",
        "third_down_engine_coverage": 1.0,
        "reliability": 0.7,
        "components": {
            "step7_away_third_down_adjustment": -0.3,
            "step7_home_third_down_adjustment": 0.1,
            "step7_total_third_down_adjustment": -0.2,
        },
    }
    html = ui._model_card_v7(_game(), _away(), _home(), output)
    assert "STEP 7 • THIRD-DOWN-ADJUSTED OVER/UNDER MODEL" in html
    assert "Step 6 50.0 → third-down adjusted 49.8" in html
    assert "Third-down coverage" in html


def test_render_wrapper_patches_v6_symbols_and_restores(monkeypatch):
    originals = {
        "hero": ui.frozen_v6._hero_v6,
        "slate": ui.frozen_v6.upgraded_slate,
        "model": ui.frozen_v6._model_card_v6,
        "components": ui.frozen_v6._components_panel_v6,
        "final": ui.frozen_v6._final_card_v6,
    }
    seen = {}

    monkeypatch.setattr(ui.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(ui.st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(ui, "_clear_stale_scan_state", lambda: None)

    def fake_render(*args, **kwargs):
        seen["hero"] = ui.frozen_v6._hero_v6
        seen["slate"] = ui.frozen_v6.upgraded_slate
        seen["model"] = ui.frozen_v6._model_card_v6
        seen["components"] = ui.frozen_v6._components_panel_v6
        seen["final"] = ui.frozen_v6._final_card_v6
        return "ok"

    monkeypatch.setattr(ui.frozen_v6, "render_over_under_hub", fake_render)

    result = ui.render_over_under_hub()

    assert result == "ok"
    assert seen["hero"] is ui._hero_v7
    assert seen["slate"] is ui.upgraded_slate
    assert seen["model"] is ui._model_card_v7
    assert seen["components"] is ui._components_panel_v7
    assert seen["final"] is ui._final_card_v7

    assert ui.frozen_v6._hero_v6 is originals["hero"]
    assert ui.frozen_v6.upgraded_slate is originals["slate"]
    assert ui.frozen_v6._model_card_v6 is originals["model"]
    assert ui.frozen_v6._components_panel_v6 is originals["components"]
    assert ui.frozen_v6._final_card_v6 is originals["final"]


def test_router_v47_only_advances_cfb_over_under(monkeypatch):
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
    router._render_nfl_or_cfb_v47("Over/Under")

    assert seen["module"] == "cfb_over_under_matchup_ui_v7"
    assert seen["market"] == "Over/Under"


def test_router_v47_delegates_other_routes(monkeypatch):
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
    router._render_nfl_or_cfb_v47("Moneyline")
    router._render_nfl_or_cfb_v47("Game Total")

    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    router._render_nfl_or_cfb_v47("Over/Under")

    assert seen == ["Moneyline", "Game Total", "Over/Under"]


def test_render_app_temporarily_patches_v46_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v46
    seen = {}

    def fake_render_app():
        seen["during"] = router.prior._render_nfl_or_cfb_v46

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)
    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v47
    assert router.prior._render_nfl_or_cfb_v46 is original
