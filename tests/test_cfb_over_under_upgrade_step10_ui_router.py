"""Regression checks for CFB O/U Upgrade Step 10 UI and Router V50."""
from __future__ import annotations
import types
import cfb_over_under_matchup_ui_v10 as ui
import streamlit_memory_lazy_router_v50 as router


def _game(): return {"game_date": "2026-09-10", "kickoff_iso": "2026-09-10T20:00:00-04:00", "away_team": "Florida A&M", "home_team": "Miami (FL)"}
def _away(): return {"team": "Florida A&M"}
def _home(): return {"team": "Miami (FL)"}


def _engine():
    return {
        "model_ready": True, "coverage": 1.0,
        "away_recent": {"games": 8, "avg_points_for": 27.1, "avg_points_against": 20.2, "avg_combined_total": 47.3},
        "home_recent": {"games": 8, "avg_points_for": 38.4, "avg_points_against": 18.6, "avg_combined_total": 57.0},
        "head_to_head": {"meetings": 1, "avg_combined_total": 65.0, "latest": {"date": "2024-09-08T01:00:00Z", "points_for": 9, "points_against": 56}},
    }


def test_hero_preserves_step9_and_adds_history(monkeypatch):
    monkeypatch.setattr(ui, "_FROZEN_STEP9_HERO", lambda *a, **k: "<STEP9/>")
    monkeypatch.setattr(ui.history_engine, "build_history_engine", lambda *a, **k: _engine())
    html = ui._hero_v10(_game(), _away(), _home())
    assert "<STEP9/>" in html
    assert "UPGRADE STEP 10" in html
    assert "CONTEXT ONLY • 0% MODEL WEIGHT" in html
    assert "Florida A&amp;M" in html
    assert "65.0" in html
    assert "2024-09-08" in html


def test_history_panel_gates_without_recent_sample(monkeypatch):
    monkeypatch.setattr(ui.history_engine, "build_history_engine", lambda *a, **k: {"model_ready": False, "reason": "insufficient history"})
    html = ui._history_panel(_game(), _away(), _home())
    assert "HISTORY GATED" in html
    assert "insufficient history" in html
    assert "Step 9 model math remains active" in html


def test_model_card_keeps_step9_output_and_adds_zero_weight_audit(monkeypatch):
    monkeypatch.setattr(ui, "_FROZEN_STEP9_MODEL_CARD", lambda *a, **k: "<STEP9MODEL/>")
    output = {"ready": True, "projected_total": 47.0, "structural_total_sigma": 14.2, "reliability": 0.73}
    html = ui._model_card_v10(_game(), _away(), _home(), output)
    assert "<STEP9MODEL/>" in html
    assert "HISTORY CONTEXT CERTIFIED" in html
    assert "47.0" in html
    assert "14.20" in html
    assert "history weight is 0%" in html


def test_components_panel_preserves_step9(monkeypatch):
    monkeypatch.setattr(ui, "_FROZEN_STEP9_COMPONENTS_PANEL", lambda output: "<STEP9COMP/>")
    output = {"ready": True, "components": {"step10_history_coverage": 1.0, "step10_away_recent_games": 8, "step10_home_recent_games": 8, "step10_h2h_meetings": 1, "step10_projected_total_adjustment": 0.0}}
    html = ui._components_panel_v10(output)
    assert "<STEP9COMP/>" in html
    assert "STEP 10 HISTORY AUDIT" in html
    assert "verified H2H meetings 1" in html


def test_router_v50_only_advances_cfb_ou(monkeypatch):
    seen = {}
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "College Football"})
    module = types.SimpleNamespace(render_cfb_hub=lambda market, *args: seen.update({"market": market}))
    monkeypatch.setattr(router.root, "_import", lambda name: (seen.update({"module": name}) or module))
    router._render_nfl_or_cfb_v50("Over/Under")
    assert seen["module"] == "cfb_over_under_matchup_ui_v10"
    assert seen["market"] == "Over/Under"


def test_router_delegates_other_routes(monkeypatch):
    seen = []
    monkeypatch.setattr(router, "_FROZEN_RENDER_NFL_OR_CFB", lambda m: seen.append(m))
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "College Football"})
    router._render_nfl_or_cfb_v50("Moneyline")
    monkeypatch.setattr(router.st, "session_state", {"ks_sport_touch": "NFL"})
    router._render_nfl_or_cfb_v50("Over/Under")
    assert seen == ["Moneyline", "Over/Under"]


def test_render_app_patches_v49_and_restores(monkeypatch):
    original = router.prior._render_nfl_or_cfb_v49; seen = {}
    monkeypatch.setattr(router.prior, "render_app", lambda: seen.update({"during": router.prior._render_nfl_or_cfb_v49}))
    router.render_app()
    assert seen["during"] is router._render_nfl_or_cfb_v50
    assert router.prior._render_nfl_or_cfb_v49 is original
