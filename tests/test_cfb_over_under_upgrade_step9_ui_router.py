"""Regression checks for CFB O/U Upgrade Step 9 UI and Router V49."""
from __future__ import annotations
import types
import cfb_over_under_matchup_ui_v9 as ui
import streamlit_memory_lazy_router_v49 as router

def _game():return {"game_date":"2026-09-10","away_team":"Florida A&M","home_team":"Miami (FL)"}
def _away():return {"team":"Florida A&M"}
def _home():return {"team":"Miami (FL)"}

def _engine():
    return {"model_ready":True,"event_id":"401858213","sigma_adjustment":0.0,"weather":{"ready":True,"temperature_f":84,"gust_mph":8,"precipitation_pct":34},"venue":{"ready":True,"name":"Hard Rock Stadium","city":"Miami Gardens","state":"FL","indoor":False},"weather_stress":{"total_stress":0.0},"away_availability":{"ready":True,"roster_total":99,"flagged_count":0,"timestamp":"2026-09-09T00:50:05Z"},"home_availability":{"ready":True,"roster_total":100,"flagged_count":0,"timestamp":"2026-09-09T00:52:18Z"}}

def test_hero_preserves_step8_and_adds_environment(monkeypatch):
    monkeypatch.setattr(ui,"_FROZEN_STEP8_HERO",lambda *a,**k:"<STEP8/>")
    monkeypatch.setattr(ui.environment_engine,"build_environment_engine",lambda *a,**k:_engine())
    html=ui._hero_v9(_game(),_away(),_home())
    assert "<STEP8/>" in html
    assert "UPGRADE STEP 9" in html
    assert "Hard Rock Stadium" in html
    assert "84°F" in html
    assert "Zero reported flags" in html
    assert "injury model weight is 0%" in html

def test_environment_panel_gates(monkeypatch):
    monkeypatch.setattr(ui.environment_engine,"build_environment_engine",lambda *a,**k:{"model_ready":False,"reason":"weather missing"})
    html=ui._environment_panel(_game(),_away(),_home())
    assert "ENVIRONMENT GATED" in html
    assert "weather missing" in html

def test_model_card_keeps_total_and_shows_sigma():
    output={"ready":True,"upgrade_step9_applied":True,"step9_base_projected_total":47.0,"step9_base_structural_total_sigma":14.0,"projected_total":47.0,"projected_away_points":20.0,"projected_home_points":27.0,"structural_total_sigma":14.2,"over_probability":0.4,"under_probability":0.6,"environment_engine_coverage":1.0,"roster_audit_coverage":1.0,"reliability":0.7,"components":{"step9_environment_sigma_adjustment":0.2,"step9_weather_stress":0.16}}
    html=ui._model_card_v9(_game(),_away(),_home(),output)
    assert "STEP 9 • ENVIRONMENT-ADJUSTED UNCERTAINTY" in html
    assert "Step 8 47.0 → Step 9 47.0 • unchanged" in html
    assert "σ 14.00 → 14.20" in html

def test_router_v49_only_advances_cfb_ou(monkeypatch):
    seen={}
    monkeypatch.setattr(router.st,"session_state",{"ks_sport_touch":"College Football"})
    module=types.SimpleNamespace(render_cfb_hub=lambda market,*args:seen.update({"market":market}))
    monkeypatch.setattr(router.root,"_import",lambda name:(seen.update({"module":name}) or module))
    router._render_nfl_or_cfb_v49("Over/Under")
    assert seen["module"]=="cfb_over_under_matchup_ui_v9"
    assert seen["market"]=="Over/Under"

def test_router_delegates_other_routes(monkeypatch):
    seen=[]
    monkeypatch.setattr(router,"_FROZEN_RENDER_NFL_OR_CFB",lambda m:seen.append(m))
    monkeypatch.setattr(router.st,"session_state",{"ks_sport_touch":"College Football"})
    router._render_nfl_or_cfb_v49("Moneyline")
    monkeypatch.setattr(router.st,"session_state",{"ks_sport_touch":"NFL"})
    router._render_nfl_or_cfb_v49("Over/Under")
    assert seen==["Moneyline","Over/Under"]

def test_render_app_patches_v48_and_restores(monkeypatch):
    original=router.prior._render_nfl_or_cfb_v48; seen={}
    monkeypatch.setattr(router.prior,"render_app",lambda:seen.update({"during":router.prior._render_nfl_or_cfb_v48}))
    router.render_app()
    assert seen["during"] is router._render_nfl_or_cfb_v49
    assert router.prior._render_nfl_or_cfb_v48 is original
