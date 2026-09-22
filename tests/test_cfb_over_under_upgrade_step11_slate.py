"""Regression checks for CFB O/U Upgrade Step 11 slate V10."""
from __future__ import annotations
import cfb_over_under_slate_v10 as slate


def _game(identity="g1"):
    return {
        "identity_key": identity, "game_id": identity,
        "away_team": "Florida A&M", "home_team": "Miami (FL)",
        "kickoff_iso": "2026-09-10T20:00:00-04:00",
        "identity_verified": True, "date_matches_query": True,
    }


def _base(game):
    raw = {
        "version": "STEP10", "ready": True,
        "projected_away_points": 20.0, "projected_home_points": 27.0,
        "projected_total": 47.0, "analysis_line": 50.5,
        "structural_total_sigma": 14.2, "reliability": 0.73,
        "over_probability": 0.41, "under_probability": 0.59, "push_probability": 0.0,
        "feature_coverage": {"score": 0.81}, "components": {},
    }
    return {
        "game": dict(game), "away": {"team": "Florida A&M"}, "home": {"team": "Miami (FL)"},
        "raw": raw, "final": {"ready": True, "rank_eligible": True},
        "history_engine": {"event_id": "401858213", "away_espn_team_id": "50", "home_espn_team_id": "2390"},
        "analysis_line": 50.5,
    }


def test_analyze_game_runs_step10_form_final(monkeypatch):
    seen = []; game = _game()
    monkeypatch.setattr(slate.frozen, "analyze_game", lambda g,d,line: (seen.append("step10") or _base(g)))
    monkeypatch.setattr(slate.form_engine, "build_form_strength_engine", lambda g,a,h,step10_history=None: (seen.append("form_build") or {"model_ready": True, "coverage": 1.0}))
    def apply(raw, engine):
        seen.append("form_apply"); out = dict(raw); out["upgrade_step11_applied"] = True; out["projected_total"] = 47.5; return out
    monkeypatch.setattr(slate.form_engine, "apply_to_raw", apply)
    monkeypatch.setattr(slate.final_model, "synthesize", lambda g,r: (seen.append("final") or {"ready": True, "projected_total": r["projected_total"]}))
    out = slate.analyze_game.__wrapped__(game, "2026-09-10", 50.5)
    assert seen == ["step10", "form_build", "form_apply", "final"]
    assert out["step10_raw"]["projected_total"] == 47.0
    assert out["raw"]["projected_total"] == 47.5
    assert out["analysis_line_form_weight"] == 0.0
    assert out["direct_selection_form_weight"] == 0.0


def test_scan_reports_form_strength(monkeypatch):
    monkeypatch.setattr(slate, "analyze_game", lambda g,d,l: {
        "game": dict(g), "raw": {"ready": True, "upgrade_step11_applied": True},
        "final": {"ready": True, "rank_eligible": False},
        "form_strength_engine": {"model_ready": True},
    })
    rows, diag = slate.scan_slate([_game()], "2026-09-10", {"g1": 50.5}, workers=1)
    assert len(rows) == 1
    assert diag["form_strength_engine_ready"] == 1
    assert diag["form_strength_engine_applied"] == 1
    assert diag["analysis_line_form_weight"] == 0.0
    assert diag["direct_selection_form_weight"] == 0.0
    assert diag["monte_carlo_used"] is False
