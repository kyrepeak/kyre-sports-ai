"""Regression checks for CFB O/U Upgrade Step 11 UI and Router V51."""
from __future__ import annotations
import types
import cfb_over_under_matchup_ui_v11 as ui
import streamlit_memory_lazy_router_v51 as router


def _game(): return {"game_date": "2026-09-10", "kickoff_iso": "2026-09-10T20:00:00-04:00", "away_team": "Florida A&M", "home_team": "Miami (FL)"}
def _away(): return {"team": "Florida A&M"}
def _home(): return {"team": "Miami (FL)"}


def _engine():
    side = {
        "ready": True, "games": 2, "avg_points_for": 31.5,
        "avg_points_against": 22.5, "opponent_record_coverage": 1.0,
        "avg_opponent_win_pct": 0.625, "sos_adjusted_points_for": 32.5,
        "sos_adjusted_points_against": 21.5, "quality_factor": 0.4,
    }
    return {"model_ready": True, "coverage": 0.4, "away_form": side, "home_form": side}


def test_hero_preserves_step10_and_adds_form(monkeypatch):
    monkeypatch.setattr(ui, "_FROZEN_STEP10_HERO", lambda *a, **k: "<STEP10/>")
    monkeypatch.setattr(ui.form_engine, "build_form_strength_engine", lambda *a, **k: _engine())
    html = ui._hero_v11(_game(), _away(), _home())
    assert "<STEP10/>" in html
    assert "UPGRADE STEP 11" in html
    assert "CURRENT SEASON ONLY" in html
    assert "Florida A&amp;M" in html
    assert "Projection blend 18%" in html


def test_form_panel_gates_safely(monkeypatch):
    monkeypatch.setattr(ui.form_engine, "build_form_strength_engine", lambda *a, **k: {"model_ready": False, "reason": "sample below minimum"})
    html = ui._form_panel(_game(), _away(), _home())
    assert "FORM GATED" in html
    assert "sample below minimum" in html
    assert "no projection is forced" in html


def test_model_card_applied_shows_bounded_delta(monkeypatch):
    monkeypatch.setattr(ui, "_FROZEN_STEP10_MODEL_CARD", lambda *a, **k: "<STEP10MODEL/>")
    output = {
        "ready": True, "upgrade_step11_applied": True,
        "step11_base_projected_total": 47.0, "projected_total": 47.6,
        "components": {"step11_total_form_adjustment": 0.6, "step11_away_form_adjustment": 0.2, "step11_home_form_adjustment": 0.4},
    }
    html = ui._model_card_v11(_game(), _away(), _home(), output)
    assert "<STEP10MODEL/>" in html
    assert "BOUNDED CURRENT-FORM ADJUSTMENT" in html
    assert "47.0" in html
    assert "47.6" in html
    assert "σ and reliability unchanged" in html


def test_router_v51_only_advances_cfb_ou(monkeypatch):
    seen = {}
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "College Football"})
    module = types.SimpleNamespace(render_cfb_hub=lambda market, *args: seen.update({"market": market}))
    monkeypatch.setattr(router.root, "_import", lambda name: (seen.update({"module": name}) or module))
    router._render_nfl_or_cfb_v51("Over/Under")
    assert seen["module"] == "cfb_over_under_matchup_ui_v11"
    assert seen["market"] == "Over/Under"


def test_router_delegates_other_routes(monkeypatch):
    seen = []
    monkeypatch.setattr(router, "_FROZEN_RENDER_NFL_OR_CFB", lambda m: seen.append(m))
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "College Football"})
    router._render_nfl_or_cfb_v51("Moneyline")
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    router._render_nfl_or_cfb_v51("Over/Under")
    assert seen == ["Moneyline", "Over/Under"]


def test_render_app_patches_v50_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v50; seen = {}
    monkeypatch.setattr(router.prior, "render_app", lambda: seen.update({"during": router.prior._render_nfl_or_cfb_v50}))
    router.render_app()
    assert seen["during"] is router._render_nfl_or_cfb_v51
    assert router.prior._render_nfl_or_cfb_v50 is original
