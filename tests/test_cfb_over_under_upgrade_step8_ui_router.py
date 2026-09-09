"""Regression checks for CFB O/U Upgrade Step 8 UI and Router V48."""
from __future__ import annotations

import types

import cfb_over_under_matchup_ui_v8 as ui
import streamlit_memory_lazy_router_v48 as router


def _game():
    return {"game_date":"2026-09-10","away_team":"Florida A&M","home_team":"Miami (FL)"}


def _away():
    return {"team":"Florida A&M"}


def _home():
    return {"team":"Miami (FL)"}


def _metrics(team,games,gained,lost):
    return {
        "team":team,
        "ready":True,
        "games":games,
        "turnovers_gained":gained,
        "turnovers_lost":lost,
        "turnover_margin":gained-lost,
        "takeaways_per_game":gained/games,
        "giveaways_per_game":lost/games,
    }


def _engine():
    return {
        "model_ready":True,
        "sigma_adjustment":0.2,
        "away_offense":{
            "offense_team":"Florida A&M","defense_team":"Miami (FL)",
            "offense_division":"FCS","defense_division":"FBS",
            "label":"NEUTRAL TURNOVER VOLATILITY","shrunk_signal":0.1,
            "coverage":1.0,"sample_factor":1/6,
            "expected_giveaways_per_game":0.25,
            "baseline_expected_giveaways_per_game":0.8,
            "offense":_metrics("Florida A&M",2,4,1),
            "defense":_metrics("Miami (FL)",1,0,1),
        },
        "home_offense":{
            "offense_team":"Miami (FL)","defense_team":"Florida A&M",
            "offense_division":"FBS","defense_division":"FCS",
            "label":"ELEVATED TURNOVER VOLATILITY","shrunk_signal":0.2,
            "coverage":1.0,"sample_factor":1/6,
            "expected_giveaways_per_game":1.5,
            "baseline_expected_giveaways_per_game":0.9,
            "offense":_metrics("Miami (FL)",1,0,1),
            "defense":_metrics("Florida A&M",2,4,1),
        },
    }


def test_hero_preserves_step7_and_adds_turnover_panel(monkeypatch):
    monkeypatch.setattr(ui,"_FROZEN_STEP7_HERO",lambda *a,**k:"<STEP7/>")
    monkeypatch.setattr(ui.turnover_engine,"build_turnover_engine",lambda *a,**k:_engine())
    html=ui._hero_v8(_game(),_away(),_home())
    assert "<STEP7/>" in html
    assert "UPGRADE STEP 8" in html
    assert "Offense turnover profile" in html
    assert "Opponent takeaway profile" in html
    assert "does not invent a points adjustment" in html


def test_turnover_panel_fails_closed(monkeypatch):
    monkeypatch.setattr(
        ui.turnover_engine,
        "build_turnover_engine",
        lambda *a,**k:{"model_ready":False,"reason":"missing turnover row"},
    )
    html=ui._turnover_panel(_game(),_away(),_home())
    assert "TURNOVER ADJUSTMENT GATED" in html
    assert "missing turnover row" in html


def test_model_card_reports_sigma_change_and_unchanged_total():
    output={
        "ready":True,
        "upgrade_step8_applied":True,
        "step8_base_projected_total":50.0,
        "step8_base_structural_total_sigma":13.5,
        "projected_total":50.0,
        "projected_away_points":20.0,
        "projected_home_points":30.0,
        "structural_total_sigma":13.8,
        "over_probability":0.49,
        "under_probability":0.51,
        "turnover_engine_coverage":1.0,
        "reliability":0.7,
        "components":{
            "step8_turnover_sigma_adjustment":0.3,
            "step8_turnover_volatility_signal":0.24,
        },
    }
    html=ui._model_card_v8(_game(),_away(),_home(),output)
    assert "STEP 8 • TURNOVER-ADJUSTED UNCERTAINTY MODEL" in html
    assert "Step 7 50.0 → Step 8 50.0 • total unchanged" in html
    assert "σ 13.50 → 13.80" in html


def test_render_wrapper_patches_v7_symbols_and_restores(monkeypatch):
    originals={
        "hero":ui.frozen_v7._hero_v7,
        "slate":ui.frozen_v7.upgraded_slate,
        "model":ui.frozen_v7._model_card_v7,
        "components":ui.frozen_v7._components_panel_v7,
        "final":ui.frozen_v7._final_card_v7,
    }
    seen={}
    monkeypatch.setattr(ui.st,"caption",lambda *a,**k:None)
    monkeypatch.setattr(ui.st,"markdown",lambda *a,**k:None)
    monkeypatch.setattr(ui,"_clear_stale_scan_state",lambda:None)
    def fake_render(*args,**kwargs):
        seen["hero"]=ui.frozen_v7._hero_v7
        seen["slate"]=ui.frozen_v7.upgraded_slate
        seen["model"]=ui.frozen_v7._model_card_v7
        seen["components"]=ui.frozen_v7._components_panel_v7
        seen["final"]=ui.frozen_v7._final_card_v7
        return "ok"
    monkeypatch.setattr(ui.frozen_v7,"render_over_under_hub",fake_render)
    result=ui.render_over_under_hub()
    assert result=="ok"
    assert seen["hero"] is ui._hero_v8
    assert seen["slate"] is ui.upgraded_slate
    assert seen["model"] is ui._model_card_v8
    assert seen["components"] is ui._components_panel_v8
    assert seen["final"] is ui._final_card_v8
    assert ui.frozen_v7._hero_v7 is originals["hero"]
    assert ui.frozen_v7.upgraded_slate is originals["slate"]


def test_router_v48_only_advances_cfb_over_under(monkeypatch):
    seen={}
    monkeypatch.setattr(router.st,"session_state",{"ks_sport_touch":"College Football"})
    module=types.SimpleNamespace(render_cfb_hub=lambda market,*args:seen.update({"market":market}))
    def fake_import(name):
        seen["module"]=name
        return module
    monkeypatch.setattr(router.root,"_import",fake_import)
    router._render_nfl_or_cfb_v48("Over/Under")
    assert seen["module"]=="cfb_over_under_matchup_ui_v8"
    assert seen["market"]=="Over/Under"


def test_router_v48_delegates_other_routes(monkeypatch):
    seen=[]
    monkeypatch.setattr(router,"_FROZEN_RENDER_NFL_OR_CFB",lambda market:seen.append(market))
    monkeypatch.setattr(router.st,"session_state",{"ks_sport_touch":"College Football"})
    router._render_nfl_or_cfb_v48("Moneyline")
    router._render_nfl_or_cfb_v48("Game Total")
    monkeypatch.setattr(router.st,"session_state",{"ks_sport_touch":"NFL"})
    router._render_nfl_or_cfb_v48("Over/Under")
    assert seen==["Moneyline","Game Total","Over/Under"]


def test_render_app_temporarily_patches_v47_and_restores(monkeypatch):
    original=router.prior._render_nfl_or_cfb_v47
    seen={}
    def fake_render_app():
        seen["during"]=router.prior._render_nfl_or_cfb_v47
    monkeypatch.setattr(router.prior,"render_app",fake_render_app)
    router.render_app()
    assert seen["during"] is router._render_nfl_or_cfb_v48
    assert router.prior._render_nfl_or_cfb_v47 is original
