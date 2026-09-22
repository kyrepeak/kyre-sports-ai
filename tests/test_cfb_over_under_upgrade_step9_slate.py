"""Regression checks for CFB O/U Upgrade Step 9 slate V8."""
from __future__ import annotations
import cfb_over_under_slate_v8 as slate

def _game(identity="g1"):
    return {"identity_key":identity,"game_id":identity,"away_team":"Florida A&M","home_team":"Miami (FL)","kickoff_iso":"2026-09-10T20:00:00-04:00","identity_verified":True,"date_matches_query":True}

def _base(game):
    return {"game":dict(game),"away":{"team":"Florida A&M"},"home":{"team":"Miami (FL)"},"raw":{"version":"STEP8","ready":True,"projected_away_points":20.0,"projected_home_points":27.0,"projected_total":47.0,"analysis_line":50.5,"structural_total_sigma":14.0,"reliability":0.7,"components":{}},"final":{"ready":True},"analysis_line":50.5}

def test_analyze_game_runs_step8_environment_final(monkeypatch):
    seen=[]; game=_game()
    monkeypatch.setattr(slate.frozen,"analyze_game",lambda g,d,line:(seen.append("step8") or _base(g)))
    monkeypatch.setattr(slate.environment_engine,"build_environment_engine",lambda g,a,h:(seen.append("env_build") or {"model_ready":True,"coverage":1.0}))
    def apply(raw,e):
        seen.append("env_apply"); out=dict(raw); out["upgrade_step9_applied"]=True; out["structural_total_sigma"]=14.2; return out
    monkeypatch.setattr(slate.environment_engine,"apply_to_raw",apply)
    monkeypatch.setattr(slate.final_model,"synthesize",lambda g,r:(seen.append("final") or {"ready":True,"sigma":r["structural_total_sigma"]}))
    out=slate.analyze_game.__wrapped__(game,"2026-09-10",50.5)
    assert seen==["step8","env_build","env_apply","final"]
    assert out["step8_raw"]["projected_total"]==47.0
    assert out["final"]["sigma"]==14.2
    assert out["injury_model_weight"]==0.0

def test_scan_reports_environment(monkeypatch):
    monkeypatch.setattr(slate,"analyze_game",lambda g,d,l:{"game":dict(g),"raw":{"ready":True,"upgrade_step9_applied":True},"final":{"ready":True,"rank_eligible":False},"environment_engine":{"model_ready":True}})
    rows,diag=slate.scan_slate([_game()],"2026-09-10",{"g1":50.5},workers=1)
    assert len(rows)==1
    assert diag["environment_engine_ready"]==1
    assert diag["environment_engine_applied"]==1
    assert diag["analysis_line_environment_weight"]==0.0
    assert diag["projected_total_environment_weight"]==0.0
    assert diag["injury_model_weight"]==0.0
