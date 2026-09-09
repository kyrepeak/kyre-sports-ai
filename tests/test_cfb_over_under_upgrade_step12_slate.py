"""Regression checks for CFB O/U Upgrade Step 12 slate V11."""
from __future__ import annotations

import copy

import cfb_over_under_slate_v11 as slate


def _base(identity="g1"):
    raw = {
        "ready": True,
        "projected_away_points": 20.0,
        "projected_home_points": 27.0,
        "projected_total": 47.0,
        "structural_total_sigma": 14.2,
        "analysis_line": 50.5,
        "over_probability": 0.4,
        "under_probability": 0.6,
        "push_probability": 0.0,
        "reliability": 0.73,
        "feature_coverage": {"score": 0.81},
        "upgrade_step11_applied": False,
    }
    return {
        "game": {"identity_key": identity, "identity_verified": True, "date_matches_query": True},
        "away": {"team": "Away"},
        "home": {"team": "Home"},
        "raw": raw,
        "final": {
            "ready": True,
            "selection_ready": False,
            "rank_eligible": False,
            "selection": "PASS",
        },
        "step10_raw": copy.deepcopy(raw),
        "form_strength_engine": {"model_ready": False},
    }


def test_attach_certificate_preserves_step11_numeric_output(monkeypatch):
    base = _base()
    monkeypatch.setattr(slate.certifier, "certify_result", lambda result: {
        "status": "CERTIFIED", "certified": True, "integrity_passed": True,
    })
    out = slate._attach_certificate(base)
    assert out["step11_raw"] == base["raw"]
    for key in (
        "projected_away_points",
        "projected_home_points",
        "projected_total",
        "structural_total_sigma",
        "analysis_line",
        "over_probability",
        "under_probability",
        "push_probability",
        "reliability",
        "feature_coverage",
    ):
        assert out["raw"][key] == base["raw"][key]
    assert out["final"] == base["final"]
    assert out["raw"]["upgrade_step12_certified"] is True
    assert out["step12_projection_math_changed"] is False
    assert out["step12_selection_math_changed"] is False


def test_analyze_game_calls_frozen_step11_then_certifies(monkeypatch):
    seen = []
    monkeypatch.setattr(slate.frozen, "analyze_game", lambda g,d,l: (seen.append("step11") or _base()))
    monkeypatch.setattr(slate, "_attach_certificate", lambda base: (seen.append("cert") or (dict(base) | {"certification": {"status": "CERTIFIED"}})))
    out = slate.analyze_game.__wrapped__({"identity_key": "g1"}, "2026-09-10", 50.5)
    assert seen == ["step11", "cert"]
    assert out["certification"]["status"] == "CERTIFIED"


def test_scan_slate_adds_certification_diagnostics(monkeypatch):
    rows = [_base("g1"), _base("g2"), _base("g3")]
    monkeypatch.setattr(slate.frozen, "scan_slate", lambda *a, **k: (rows, {"games_analyzed": 3}))
    statuses = iter(("CERTIFIED", "DATA_GATED", "INTEGRITY_FAIL"))

    def attach(row):
        status = next(statuses)
        out = dict(row)
        out["certification"] = {
            "status": status,
            "integrity_passed": status != "INTEGRITY_FAIL",
        }
        return out

    monkeypatch.setattr(slate, "_attach_certificate", attach)
    out, diag = slate.scan_slate([], "2026-09-10", {}, workers=1)
    assert len(out) == 3
    assert diag["step12_certified_games"] == 1
    assert diag["step12_data_gated_games"] == 1
    assert diag["step12_integrity_failed_games"] == 1
    assert diag["step12_integrity_pass_rate"] == 2/3
    assert diag["step12_projection_math_changed"] is False
    assert diag["monte_carlo_used"] is False
