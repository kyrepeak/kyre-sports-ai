"""Regression checks for CFB O/U Intelligence V2 Upgrade Step 3 UI."""
from __future__ import annotations

import inspect

import cfb_over_under_matchup_ui_v3 as ui


def _engine_result():
    dims = {}
    for key, *_ in ui.engine._DIMENSIONS:
        dims[key] = {
            "label": key.replace("_", " ").title(),
            "ready": True,
            "offense_rank": 10,
            "defense_rank": 90,
            "edge": 0.50,
            "weight": 0.1,
            "weighted_edge": 0.05,
            "edge_label": "STRONG OFFENSE EDGE",
        }
    side = {
        "offense_team": "Oklahoma",
        "defense_team": "Michigan",
        "dimensions": dims,
        "coverage": 1.0,
        "points_adjustment": 2.25,
        "overall": "OFFENSE ADVANTAGE",
        "model_ready": True,
    }
    home = dict(side)
    home["offense_team"] = "Michigan"
    home["defense_team"] = "Oklahoma"
    home["points_adjustment"] = -0.75
    home["overall"] = "DEFENSE ADVANTAGE"
    return {
        "ready": True,
        "model_ready": True,
        "same_division": True,
        "division": "FBS",
        "coverage": 1.0,
        "away_offense": side,
        "home_offense": home,
    }


def test_engine_panel_shows_both_offense_vs_defense_battles(monkeypatch):
    monkeypatch.setattr(ui.engine, "build_matchup_engine", lambda *a, **k: _engine_result())

    html = ui._engine_panel(
        {"game_date": "2026-09-12"},
        {"team": "Oklahoma"},
        {"team": "Michigan"},
    )

    assert "OFFENSE VS DEFENSE ENGINE" in html
    assert "Oklahoma offense" in html
    assert "Michigan defense" in html
    assert "Michigan offense" in html
    assert "Oklahoma defense" in html
    assert "+2.25" in html
    assert "-0.75" in html
    assert any(token in html for token in ("3rd Down", "3rd down", "Third Down"))
    assert "Red Zone" in html or "Red zone" in html
    assert "Sack Pressure" in html or "Sack pressure" in html
    assert any(token in html for token in ("Turnover Pressure", "Turnover pressure", "Turnovers"))
    assert "analysis line has 0% matchup weight" in html


def test_engine_panel_fails_closed(monkeypatch):
    monkeypatch.setattr(
        ui.engine,
        "build_matchup_engine",
        lambda *a, **k: {
            "ready": True,
            "model_ready": False,
            "reason": "cross-division rank pools are not directly comparable",
        },
    )
    html = ui._engine_panel({}, {}, {})
    assert "Step-3 adjustment is gated" in html
    assert "cross-division rank pools" in html
    assert "Frozen Step-8 projection remains active" in html


def test_model_card_exposes_base_to_matchup_adjusted_total():
    html = ui._model_card_v3(
        {},
        {"team": "Oklahoma"},
        {"team": "Michigan"},
        {
            "ready": True,
            "upgrade_step3_applied": True,
            "base_projected_total": 54.0,
            "projected_total": 56.5,
            "projected_away_points": 29.0,
            "projected_home_points": 27.5,
            "analysis_line": 50.5,
            "over_probability": 0.64,
            "under_probability": 0.36,
            "push_probability": 0.0,
            "model_lean": "OVER",
            "matchup_engine_coverage": 0.88,
            "reliability": 0.84,
            "structural_total_sigma": 13.5,
            "components": {
                "step3_away_matchup_adjustment": 2.0,
                "step3_home_matchup_adjustment": 0.5,
            },
        },
    )
    assert "MATCHUP-ADJUSTED OVER/UNDER MODEL" in html
    assert "Frozen base 54.0" in html
    assert "matchup adjusted 56.5" in html
    assert "OVER 64.0%" in html
    assert "LINE WEIGHT 0%" in html


def test_enhanced_hero_keeps_frozen_step2_and_appends_engine(monkeypatch):
    monkeypatch.setattr(ui, "_FROZEN_STEP2_HERO", lambda *a, **k: "<STEP2>rankings</STEP2>")
    monkeypatch.setattr(ui, "_engine_panel", lambda *a, **k: "<STEP3>engine</STEP3>")
    assert ui._enhanced_hero_v3({}, {}, {}) == "<STEP2>rankings</STEP2><STEP3>engine</STEP3>"


def test_final_card_keeps_step9_rules_but_updates_explanation(monkeypatch):
    monkeypatch.setattr(
        ui,
        "_FROZEN_FINAL_CARD",
        lambda *a, **k: (
            "STEP 9 • FINAL OVER/UNDER SELECTION "
            "The final rule does not change Step-8 projection math."
        ),
    )
    html = ui._final_card_v3({}, {})
    assert "STEP 9 FINAL RULES • STEP 3 MATCHUP-ADJUSTED PROJECTION" in html
    assert "Step-9 qualification thresholds remain frozen" in html


def test_wrapper_temporarily_patches_hub_and_restores(monkeypatch):
    original_hero = ui.frozen_v2._enhanced_hero_v2
    original_slate = ui._HUB3.slate
    original_model_card = ui._HUB2._model_card
    original_components = ui._HUB2._components_panel
    original_final_card = ui._HUB3._final_card
    seen = {}

    monkeypatch.setattr(ui.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(ui.st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(ui.st, "session_state", {})

    def fake_render(*args, **kwargs):
        seen["hero"] = ui.frozen_v2._enhanced_hero_v2
        seen["slate"] = ui._HUB3.slate
        seen["model_card"] = ui._HUB2._model_card
        seen["components"] = ui._HUB2._components_panel
        seen["final_card"] = ui._HUB3._final_card
        return "ok"

    monkeypatch.setattr(ui.frozen_v2, "render_over_under_hub", fake_render)
    result = ui.render_over_under_hub()

    assert result == "ok"
    assert seen["hero"] is ui._enhanced_hero_v3
    assert seen["slate"] is ui.upgraded_slate
    assert seen["model_card"] is ui._model_card_v3
    assert seen["components"] is ui._components_panel_v3
    assert seen["final_card"] is ui._final_card_v3

    assert ui.frozen_v2._enhanced_hero_v2 is original_hero
    assert ui._HUB3.slate is original_slate
    assert ui._HUB2._model_card is original_model_card
    assert ui._HUB2._components_panel is original_components
    assert ui._HUB3._final_card is original_final_card


def test_step3_ui_has_no_direct_market_or_simulation_logic():
    source = inspect.getsource(ui).lower()
    assert ui.FROZEN_UPGRADE == "cfb_over_under_matchup_ui_v2"
    assert ui.MARKET == "Over/Under"

    forbidden = (
        "import requests",
        "sportsbook_price",
        "expected_value",
        "np.random",
        "random.",
    )
    for token in forbidden:
        assert token not in source
