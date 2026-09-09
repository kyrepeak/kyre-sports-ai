"""Regression checks for CFB O/U Upgrade Step 8 slate V7."""
from __future__ import annotations

import cfb_over_under_slate_v7 as slate


def _game(identity="g1"):
    return {
        "identity_key":identity,
        "game_id":identity,
        "away_team":"Florida A&M",
        "home_team":"Miami (FL)",
        "kickoff_iso":"2026-09-10T20:00:00-04:00",
        "identity_verified":True,
        "date_matches_query":True,
    }


def _base(game):
    return {
        "game":dict(game),
        "away":{"team":"Florida A&M"},
        "home":{"team":"Miami (FL)"},
        "raw":{
            "version":"STEP7",
            "ready":True,
            "projected_away_points":20.0,
            "projected_home_points":30.0,
            "projected_total":50.0,
            "analysis_line":50.5,
            "structural_total_sigma":13.5,
            "reliability":0.7,
            "components":{},
        },
        "final":{"ready":True},
        "analysis_line":50.5,
    }


def test_analyze_game_runs_step7_then_turnover_then_final(monkeypatch):
    game=_game()
    seen=[]
    monkeypatch.setattr(slate.frozen,"analyze_game",lambda g,d,line:(seen.append("step7") or _base(g)))
    monkeypatch.setattr(
        slate.turnover_engine,
        "build_turnover_engine",
        lambda g,a,h:(seen.append("to_build") or {"model_ready":True,"coverage":1.0}),
    )
    def apply(base_raw,engine):
        seen.append("to_apply")
        out=dict(base_raw)
        out["upgrade_step8_applied"]=True
        out["structural_total_sigma"]=14.0
        return out
    monkeypatch.setattr(slate.turnover_engine,"apply_to_raw",apply)
    monkeypatch.setattr(
        slate.final_model,
        "synthesize",
        lambda g,raw:(seen.append("final") or {"ready":True,"sigma":raw["structural_total_sigma"]}),
    )
    out=slate.analyze_game.__wrapped__(game,"2026-09-10",50.5)
    assert seen == ["step7","to_build","to_apply","final"]
    assert out["step7_raw"]["projected_total"] == 50.0
    assert out["raw"]["upgrade_step8_applied"] is True
    assert out["final"]["sigma"] == 14.0
    assert out["analysis_line_turnover_weight"] == 0.0
    assert out["projected_total_turnover_weight"] == 0.0


def test_scan_slate_reports_turnover_engine(monkeypatch):
    games=[_game("g1"),_game("g2")]
    def fake_analyze(game,day,line):
        return {
            "game":dict(game),
            "raw":{"ready":True,"upgrade_step8_applied":True},
            "final":{"ready":True,"rank_eligible":game["identity_key"]=="g1"},
            "turnover_engine":{"model_ready":True},
        }
    monkeypatch.setattr(slate,"analyze_game",fake_analyze)
    rows,diag=slate.scan_slate(games,"2026-09-10",{"g1":50.5,"g2":48.5},workers=1)
    assert len(rows)==2
    assert diag["turnover_engine_ready"]==2
    assert diag["turnover_engine_applied"]==2
    assert diag["qualified_plays"]==1
    assert diag["analysis_line_turnover_weight"]==0.0
    assert diag["projected_total_turnover_weight"]==0.0
    assert diag["monte_carlo_used"] is False
