"""Regression checks for CFB O/U Upgrade Step 4 UI and Router V44."""
from __future__ import annotations

import types

import cfb_over_under_matchup_ui_v4 as ui
import streamlit_memory_lazy_router_v44 as router


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


def _pace():
    return {
        "model_ready": True,
        "pace_label": "FAST",
        "away": {
            "team": "Florida A&M",
            "division": "FCS",
            "plays_per_game": 71.0,
            "seconds_per_offensive_play": 25.8,
            "pace_index": 1.04,
        },
        "home": {
            "team": "Miami (FL)",
            "division": "FBS",
            "plays_per_game": 75.0,
            "seconds_per_offensive_play": 24.7,
            "pace_index": 1.07,
        },
        "expected_combined_plays": 145.0,
        "division_baseline_combined_plays": 138.0,
        "historical_combined_plays_per_game": 146.0,
        "clock_implied_combined_plays": 142.0,
        "sample_factor": 0.4,
        "coverage": 1.0,
        "total_points_adjustment": 1.2,
        "direct_possessions_available": False,
        "expected_combined_possessions": None,
    }


def test_step4_hero_preserves_logo_hero_and_adds_pace(monkeypatch):
    monkeypatch.setattr(ui, "_FROZEN_LOGO_HERO", lambda *a, **k: "<LOGOS/>")
    monkeypatch.setattr(ui.pace_engine, "build_pace_engine", lambda *a, **k: _pace())

    html = ui._hero_v4(_game(), _away(), _home())

    assert "<LOGOS/>" in html
    assert "UPGRADE STEP 4" in html
    assert "Expected combined plays" in html
    assert "145.0" in html
    assert "Direct expected possessions" in html
    assert "—" in html


def test_pace_panel_fails_closed_when_evidence_missing(monkeypatch):
    monkeypatch.setattr(
        ui.pace_engine,
        "build_pace_engine",
        lambda *a, **k: {
            "model_ready": False,
            "reason": "missing NCAA pace rows",
        },
    )
    html = ui._pace_panel(_game(), _away(), _home())
    assert "PACE ADJUSTMENT GATED" in html
    assert "missing NCAA pace rows" in html


def test_step4_model_card_reports_step3_to_pace_transition():
    output = {
        "ready": True,
        "upgrade_step4_applied": True,
        "step4_base_projected_total": 50.0,
        "projected_total": 51.2,
        "projected_away_points": 20.5,
        "projected_home_points": 30.7,
        "analysis_line": 50.5,
        "over_probability": 0.53,
        "under_probability": 0.47,
        "push_probability": 0.0,
        "model_lean": "OVER",
        "expected_combined_plays": 145.0,
        "pace_engine_coverage": 1.0,
        "reliability": 0.7,
        "components": {
            "step4_total_pace_adjustment": 1.2,
            "step4_pace_ratio": 1.05,
        },
    }
    html = ui._model_card_v4(_game(), _away(), _home(), output)
    assert "STEP 4 • PACE-ADJUSTED OVER/UNDER MODEL" in html
    assert "Step 3 50.0 → pace adjusted 51.2" in html
    assert "Expected plays" in html


def test_render_wrapper_patches_step3_symbols_and_restores(monkeypatch):
    originals = {
        "hero": ui.frozen_logo_v4._hero_with_multisource_logos,
        "slate": ui.step3.upgraded_slate,
        "model": ui.step3._model_card_v3,
        "components": ui.step3._components_panel_v3,
        "final": ui.step3._final_card_v3,
    }
    seen = {}

    monkeypatch.setattr(ui.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(ui.st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(ui, "_clear_stale_scan_state", lambda: None)

    def fake_render(*args, **kwargs):
        seen["hero"] = ui.frozen_logo_v4._hero_with_multisource_logos
        seen["slate"] = ui.step3.upgraded_slate
        seen["model"] = ui.step3._model_card_v3
        seen["components"] = ui.step3._components_panel_v3
        seen["final"] = ui.step3._final_card_v3
        return "ok"

    monkeypatch.setattr(ui.frozen_logo_v4, "render_over_under_hub", fake_render)

    result = ui.render_over_under_hub()

    assert result == "ok"
    assert seen["hero"] is ui._hero_v4
    assert seen["slate"] is ui.upgraded_slate
    assert seen["model"] is ui._model_card_v4
    assert seen["components"] is ui._components_panel_v4
    assert seen["final"] is ui._final_card_v4

    assert ui.frozen_logo_v4._hero_with_multisource_logos is originals["hero"]
    assert ui.step3.upgraded_slate is originals["slate"]
    assert ui.step3._model_card_v3 is originals["model"]
    assert ui.step3._components_panel_v3 is originals["components"]
    assert ui.step3._final_card_v3 is originals["final"]


def test_router_v44_only_advances_cfb_over_under(monkeypatch):
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
    router._render_nfl_or_cfb_v44("Over/Under")

    assert seen["module"] == "cfb_over_under_matchup_ui_v4"
    assert seen["market"] == "Over/Under"


def test_router_v44_delegates_other_markets_and_non_cfb(monkeypatch):
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
    router._render_nfl_or_cfb_v44("Moneyline")
    router._render_nfl_or_cfb_v44("Game Total")

    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    router._render_nfl_or_cfb_v44("Over/Under")

    assert seen == ["Moneyline", "Game Total", "Over/Under"]


def test_render_app_temporarily_patches_v43_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v43
    seen = {}

    def fake_render_app():
        seen["during"] = router.prior._render_nfl_or_cfb_v43

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)
    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v44
    assert router.prior._render_nfl_or_cfb_v43 is original
