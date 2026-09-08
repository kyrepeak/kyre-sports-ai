"""Regression checks for CFB O/U Upgrade Step 6 UI and Router V46."""
from __future__ import annotations

import types

import cfb_over_under_matchup_ui_v6 as ui
import streamlit_memory_lazy_router_v46 as router


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


def _metrics(team, attempts, td_rate, score_rate, ppt, apg):
    return {
        "team": team,
        "ready": True,
        "attempts": attempts,
        "touchdown_rate": td_rate,
        "scoring_rate": score_rate,
        "points_per_trip": ppt,
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
            "label": "BALANCED",
            "points_adjustment": 0.05,
            "coverage": 1.0,
            "sample_factor": 0.17,
            "offense": _metrics("Florida A&M", 7, 2/7, 6/7, 26/7, 3.5),
            "defense": _metrics("Miami (FL)", 2, 0.0, 1.0, 3.0, 2.0),
        },
        "home_offense": {
            "offense_team": "Miami (FL)",
            "defense_team": "Florida A&M",
            "offense_division": "FBS",
            "defense_division": "FCS",
            "label": "RED-ZONE EDGE",
            "points_adjustment": 0.20,
            "coverage": 1.0,
            "sample_factor": 0.25,
            "offense": _metrics("Miami (FL)", 3, 1.0, 1.0, 7.0, 3.0),
            "defense": _metrics("Florida A&M", 5, 0.6, 0.6, 4.2, 2.5),
        },
    }


def test_hero_preserves_step5_and_adds_red_zone_panel(monkeypatch):
    monkeypatch.setattr(ui, "_FROZEN_STEP5_HERO", lambda *a, **k: "<STEP5/>")
    monkeypatch.setattr(
        ui.red_zone_engine,
        "build_red_zone_engine",
        lambda *a, **k: _engine(),
    )

    html = ui._hero_v6(_game(), _away(), _home())

    assert "<STEP5/>" in html
    assert "UPGRADE STEP 6" in html
    assert "Red-zone offense" in html
    assert "Opponent red-zone defense" in html
    assert "Touchdown conversion carries 65%" in html


def test_red_zone_panel_fails_closed(monkeypatch):
    monkeypatch.setattr(
        ui.red_zone_engine,
        "build_red_zone_engine",
        lambda *a, **k: {
            "model_ready": False,
            "reason": "missing direct red-zone row",
        },
    )
    html = ui._red_zone_panel(_game(), _away(), _home())
    assert "RED-ZONE ADJUSTMENT GATED" in html
    assert "missing direct red-zone row" in html


def test_model_card_reports_step5_to_step6_transition():
    output = {
        "ready": True,
        "upgrade_step6_applied": True,
        "step6_base_projected_total": 50.0,
        "projected_total": 50.3,
        "projected_away_points": 20.1,
        "projected_home_points": 30.2,
        "analysis_line": 50.5,
        "over_probability": 0.49,
        "under_probability": 0.51,
        "push_probability": 0.0,
        "model_lean": "UNDER",
        "red_zone_engine_coverage": 1.0,
        "reliability": 0.7,
        "components": {
            "step6_away_red_zone_adjustment": 0.1,
            "step6_home_red_zone_adjustment": 0.2,
            "step6_total_red_zone_adjustment": 0.3,
        },
    }
    html = ui._model_card_v6(_game(), _away(), _home(), output)
    assert "STEP 6 • RED-ZONE-ADJUSTED OVER/UNDER MODEL" in html
    assert "Step 5 50.0 → red-zone adjusted 50.3" in html
    assert "Red-zone coverage" in html


def test_render_wrapper_patches_v5_symbols_and_restores(monkeypatch):
    originals = {
        "hero": ui.frozen_v5._hero_v5,
        "slate": ui.frozen_v5.upgraded_slate,
        "model": ui.frozen_v5._model_card_v5,
        "components": ui.frozen_v5._components_panel_v5,
        "final": ui.frozen_v5._final_card_v5,
    }
    seen = {}

    monkeypatch.setattr(ui.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(ui.st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(ui, "_clear_stale_scan_state", lambda: None)

    def fake_render(*args, **kwargs):
        seen["hero"] = ui.frozen_v5._hero_v5
        seen["slate"] = ui.frozen_v5.upgraded_slate
        seen["model"] = ui.frozen_v5._model_card_v5
        seen["components"] = ui.frozen_v5._components_panel_v5
        seen["final"] = ui.frozen_v5._final_card_v5
        return "ok"

    monkeypatch.setattr(ui.frozen_v5, "render_over_under_hub", fake_render)

    result = ui.render_over_under_hub()

    assert result == "ok"
    assert seen["hero"] is ui._hero_v6
    assert seen["slate"] is ui.upgraded_slate
    assert seen["model"] is ui._model_card_v6
    assert seen["components"] is ui._components_panel_v6
    assert seen["final"] is ui._final_card_v6

    assert ui.frozen_v5._hero_v5 is originals["hero"]
    assert ui.frozen_v5.upgraded_slate is originals["slate"]
    assert ui.frozen_v5._model_card_v5 is originals["model"]
    assert ui.frozen_v5._components_panel_v5 is originals["components"]
    assert ui.frozen_v5._final_card_v5 is originals["final"]


def test_router_v46_only_advances_cfb_over_under(monkeypatch):
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
    router._render_nfl_or_cfb_v46("Over/Under")

    assert seen["module"] == "cfb_over_under_matchup_ui_v6"
    assert seen["market"] == "Over/Under"


def test_router_v46_delegates_other_routes(monkeypatch):
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
    router._render_nfl_or_cfb_v46("Moneyline")
    router._render_nfl_or_cfb_v46("Game Total")

    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    router._render_nfl_or_cfb_v46("Over/Under")

    assert seen == ["Moneyline", "Game Total", "Over/Under"]


def test_render_app_temporarily_patches_v45_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v45
    seen = {}

    def fake_render_app():
        seen["during"] = router.prior._render_nfl_or_cfb_v45

    monkeypatch.setattr(router.prior, "render_app", fake_render_app)
    router.render_app()

    assert seen["during"] is router._render_nfl_or_cfb_v46
    assert router.prior._render_nfl_or_cfb_v45 is original
