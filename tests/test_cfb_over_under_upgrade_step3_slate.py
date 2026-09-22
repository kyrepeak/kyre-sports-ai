"""Regression checks for CFB O/U Upgrade Step 3 slate orchestration."""
from __future__ import annotations

import cfb_over_under_slate_v2 as slate


def _game():
    return {
        "identity_key": "ncaa:123",
        "game_id": "123",
        "away_team": "Oklahoma",
        "home_team": "Michigan",
        "kickoff_iso": "2026-09-12T12:00:00-04:00",
        "identity_verified": True,
        "date_matches_query": True,
    }


def _base_result():
    return {
        "game": _game(),
        "away": {"team": "Oklahoma"},
        "home": {"team": "Michigan"},
        "raw": {
            "version": "frozen",
            "ready": True,
            "analysis_line": 50.5,
            "projected_away_points": 27.0,
            "projected_home_points": 27.0,
            "projected_total": 54.0,
            "over_probability": 0.60,
            "under_probability": 0.40,
            "push_probability": 0.0,
            "reliability": 0.85,
            "feature_coverage": {"score": 0.85},
            "confidence": "MEDIUM",
            "structural_total_sigma": 13.5,
            "components": {},
        },
        "final": {"selection": "OVER"},
        "team_diag": {},
        "analysis_line": 50.5,
    }


def test_analyze_game_runs_frozen_then_step3_then_unchanged_final(monkeypatch):
    seen = {}

    monkeypatch.setattr(
        slate.frozen,
        "analyze_game",
        lambda game, day, line: _base_result(),
    )

    def build(game, away, home):
        seen["build"] = (away["team"], home["team"])
        return {
            "model_ready": True,
            "coverage": 1.0,
            "away_offense": {"points_adjustment": 1.0},
            "home_offense": {"points_adjustment": 2.0},
        }

    def apply(raw, engine):
        out = dict(raw)
        out["projected_total"] = 57.0
        out["upgrade_step3_applied"] = True
        return out

    def synthesize(game, raw):
        seen["final_raw_total"] = raw["projected_total"]
        return {"ready": True, "selection": "OVER", "rank_eligible": True}

    monkeypatch.setattr(slate.matchup_engine, "build_matchup_engine", build)
    monkeypatch.setattr(slate.matchup_engine, "apply_to_raw", apply)
    monkeypatch.setattr(slate.final_model, "synthesize", synthesize)

    out = slate.analyze_game.__wrapped__(_game(), "2026-09-12", 50.5)

    assert seen["build"] == ("Oklahoma", "Michigan")
    assert seen["final_raw_total"] == 57.0
    assert out["raw"]["projected_total"] == 57.0
    assert out["base_raw"]["projected_total"] == 54.0
    assert out["final"]["selection"] == "OVER"
    assert out["analysis_line_matchup_weight"] == 0.0


def test_scan_slate_reports_engine_ready_and_applied(monkeypatch):
    def fake_analyze(game, day, line):
        return {
            "game": dict(game),
            "raw": {"ready": True, "upgrade_step3_applied": True},
            "final": {"ready": True, "rank_eligible": True},
            "matchup_engine": {"model_ready": True},
        }

    monkeypatch.setattr(slate, "analyze_game", fake_analyze)

    rows, diag = slate.scan_slate(
        [_game()],
        "2026-09-12",
        {"ncaa:123": 50.5},
        workers=1,
    )

    assert len(rows) == 1
    assert diag["games_analyzed"] == 1
    assert diag["matchup_engine_ready"] == 1
    assert diag["matchup_engine_applied"] == 1
    assert diag["qualified_plays"] == 1
    assert diag["analysis_line_projection_weight"] == 0.0
    assert diag["analysis_line_matchup_weight"] == 0.0
    assert diag["sportsbook_input_used"] is False
    assert diag["monte_carlo_used"] is False
