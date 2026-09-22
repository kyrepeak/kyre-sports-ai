"""Regression checks for CFB O/U Upgrade Step 11 form + schedule strength."""
from __future__ import annotations

import cfb_over_under_form_strength_engine_v1 as form


def _event(event_id, date, team_id="50", opp_id="900", pf=30, pa=20, opp_record="3-1", completed=True):
    return {
        "id": str(event_id),
        "date": date,
        "status": {"type": {"completed": completed, "name": "STATUS_FINAL" if completed else "STATUS_SCHEDULED"}},
        "competitions": [{
            "id": str(event_id),
            "competitors": [
                {
                    "homeAway": "away",
                    "team": {"id": str(team_id), "displayName": f"Team {team_id}"},
                    "score": {"value": pf},
                    "records": [{"type": "total", "summary": "2-2"}],
                },
                {
                    "homeAway": "home",
                    "team": {"id": str(opp_id), "displayName": f"Team {opp_id}"},
                    "score": {"value": pa},
                    "records": [{"type": "total", "summary": opp_record}] if opp_record is not None else [],
                },
            ],
        }],
    }


def _game():
    return {
        "game_date": "2026-09-10",
        "kickoff_iso": "2026-09-10T20:00:00-04:00",
        "away_team": "Florida A&M",
        "home_team": "Miami (FL)",
    }


def test_record_pct_parses_wins_losses_ties():
    assert form._record_pct("3-1") == 0.75
    assert form._record_pct("2-1-1") == 0.625
    assert form._record_pct("0-0") is None
    assert form._record_pct("bad") is None


def test_event_row_reads_exact_opponent_record():
    row = form._event_row_with_opponent_record(
        _event("a", "2026-09-01T20:00:00Z", opp_record="3-1"),
        "50",
    )
    assert row["points_for"] == 30.0
    assert row["points_against"] == 20.0
    assert row["opponent_id"] == "900"
    assert row["opponent_record_pct"] == 0.75


def test_current_season_rows_exclude_previous_target_future_and_incomplete():
    payload = {"events": [
        _event("prev", "2025-12-01T20:00:00Z"),
        _event("old1", "2026-08-29T20:00:00Z"),
        _event("old2", "2026-09-05T20:00:00Z"),
        _event("target", "2026-09-11T00:00:00Z"),
        _event("future", "2026-09-20T00:00:00Z"),
        _event("scheduled", "2026-09-06T20:00:00Z", completed=False),
    ]}
    rows = form._current_season_rows(
        payload,
        "50",
        2026,
        form._parse_dt("2026-09-11T00:00:00Z"),
        excluded_event_id="target",
    )
    assert [row["event_id"] for row in rows] == ["old2", "old1"]
    assert all(row["date_dt"].year == 2026 for row in rows)


def test_side_form_uses_sample_and_opponent_record_coverage():
    rows = [
        {"points_for": 30.0, "points_against": 20.0, "opponent_record_pct": 0.75},
        {"points_for": 20.0, "points_against": 30.0, "opponent_record_pct": 0.50},
    ]
    out = form._side_form(rows)
    assert out["ready"] is True
    assert out["games"] == 2
    assert out["avg_points_for"] == 25.0
    assert out["avg_points_against"] == 25.0
    assert out["opponent_record_coverage"] == 1.0
    assert out["avg_opponent_win_pct"] == 0.625
    assert out["sos_signal"] == 0.25
    assert out["sos_adjusted_points_for"] == 26.0
    assert out["sos_adjusted_points_against"] == 24.0
    assert out["sample_factor"] == 0.4
    assert out["quality_factor"] == 0.4


def test_side_form_gates_low_record_coverage():
    rows = [
        {"points_for": 30.0, "points_against": 20.0, "opponent_record_pct": 0.75},
        {"points_for": 20.0, "points_against": 30.0, "opponent_record_pct": None},
    ]
    out = form._side_form(rows)
    assert out["ready"] is False
    assert out["opponent_record_coverage"] == 0.5




def test_opponent_schedule_record_fallback_uses_only_pre_target_games(monkeypatch):
    payload = {"events": [
        _event("o1", "2026-08-29T20:00:00Z", team_id="900", opp_id="701", pf=24, pa=17, opp_record=None),
        _event("o2", "2026-09-05T20:00:00Z", team_id="900", opp_id="702", pf=14, pa=21, opp_record=None),
        _event("future", "2026-09-20T20:00:00Z", team_id="900", opp_id="703", pf=50, pa=0, opp_record=None),
        _event("prior", "2025-09-01T20:00:00Z", team_id="900", opp_id="704", pf=50, pa=0, opp_record=None),
    ]}
    monkeypatch.setattr(form.history_engine, "_fetch_team_schedule", lambda team_id, season: (payload, []))
    pct, games, _ = form._opponent_schedule_record_pct(
        "900", 2026, form._parse_dt("2026-09-11T00:00:00Z")
    )
    assert games == 2
    assert pct == 0.5

    rows = [{
        "event_id": "x", "opponent_id": "900", "points_for": 30.0,
        "points_against": 20.0, "opponent_record_pct": None,
    }]
    hydrated, diag = form._hydrate_opponent_records(
        rows, 2026, form._parse_dt("2026-09-11T00:00:00Z")
    )
    assert hydrated[0]["opponent_record_pct"] == 0.5
    assert "completed games before target" in hydrated[0]["opponent_record_source"]
    assert diag["fallback_requested"] == 1
    assert diag["fallback_resolved"] == 1

def test_build_engine_exact_ids_current_season_only(monkeypatch):
    away_payload = {"events": [
        _event("a1", "2026-08-29T20:00:00Z", team_id="50", opp_id="901", pf=28, pa=21, opp_record="3-1"),
        _event("a2", "2026-09-05T20:00:00Z", team_id="50", opp_id="902", pf=35, pa=24, opp_record="2-1"),
        _event("a_prev", "2025-09-01T20:00:00Z", team_id="50", opp_id="903", pf=50, pa=10, opp_record="10-2"),
    ]}
    home_payload = {"events": [
        _event("h1", "2026-08-30T20:00:00Z", team_id="2390", opp_id="801", pf=42, pa=14, opp_record="2-2"),
        _event("h2", "2026-09-06T20:00:00Z", team_id="2390", opp_id="802", pf=38, pa=17, opp_record="3-1"),
    ]}

    def fetch(team_id, season):
        assert season == 2026
        return (away_payload if str(team_id) == "50" else home_payload), []

    monkeypatch.setattr(form.history_engine, "_fetch_team_schedule", fetch)
    history = {
        "event_id": "401858213",
        "away_espn_team_id": "50",
        "home_espn_team_id": "2390",
    }
    out = form.build_form_strength_engine(
        _game(),
        {"team": "Florida A&M"},
        {"team": "Miami (FL)"},
        step10_history=history,
    )
    assert out["model_ready"] is True
    assert out["away_form"]["games"] == 2
    assert out["home_form"]["games"] == 2
    assert all(row["date_dt"].year == 2026 for row in out["away_form"]["sample"])
    assert out["current_season_only"] is True
    assert out["previous_season_projection_weight"] == 0.0
    assert out["future_event_leakage_allowed"] is False


def test_build_engine_fails_closed_without_ids():
    out = form.build_form_strength_engine(
        _game(), {}, {}, step10_history={"event_id": "x"}
    )
    assert out["model_ready"] is False
    assert out["coverage"] == 0.0
    assert "team IDs" in out["reason"]


def test_apply_to_raw_is_bounded_and_preserves_frozen_invariants():
    base = {
        "version": "STEP10", "ready": True,
        "projected_away_points": 20.0, "projected_home_points": 27.0,
        "projected_total": 47.0, "structural_total_sigma": 14.2,
        "over_probability": 0.40, "under_probability": 0.60, "push_probability": 0.0,
        "reliability": 0.73, "analysis_line": 50.5,
        "feature_coverage": {"score": 0.81},
        "components": {"step10_history_coverage": 1.0},
    }
    strong = {
        "ready": True, "games": 5, "quality_factor": 1.0,
        "sos_adjusted_points_for": 60.0, "sos_adjusted_points_against": 10.0,
    }
    weak_def = {
        "ready": True, "games": 5, "quality_factor": 1.0,
        "sos_adjusted_points_for": 10.0, "sos_adjusted_points_against": 60.0,
    }
    engine = {
        "model_ready": True, "coverage": 1.0,
        "away_form": strong, "home_form": weak_def,
    }
    out = form.apply_to_raw(base, engine)
    assert out["upgrade_step11_applied"] is True
    assert abs(out["projected_away_points"] - 20.0) <= form.MAX_TEAM_FORM_ADJUSTMENT
    assert abs(out["projected_home_points"] - 27.0) <= form.MAX_TEAM_FORM_ADJUSTMENT
    assert abs(out["projected_total"] - 47.0) <= form.MAX_TOTAL_FORM_ADJUSTMENT + 1e-9
    assert out["structural_total_sigma"] == 14.2
    assert out["reliability"] == 0.73
    assert out["feature_coverage"] == {"score": 0.81}
    assert out["analysis_line"] == 50.5
    assert out["analysis_line_form_weight"] == 0.0
    assert out["direct_selection_form_weight"] == 0.0
    assert out["previous_season_projection_weight"] == 0.0
    assert out["components"]["step10_history_coverage"] == 1.0
    assert out["components"]["step11_structural_sigma_adjustment"] == 0.0
    assert out["components"]["step11_reliability_adjustment"] == 0.0


def test_apply_gated_preserves_step10_math_exactly():
    base = {
        "version": "STEP10", "ready": True,
        "projected_away_points": 20.0, "projected_home_points": 27.0,
        "projected_total": 47.0, "structural_total_sigma": 14.2,
        "reliability": 0.73, "analysis_line": 50.5,
        "over_probability": 0.4, "under_probability": 0.6,
        "feature_coverage": {"score": 0.81}, "components": {},
    }
    out = form.apply_to_raw(base, {"model_ready": False, "reason": "sample low"})
    for key in (
        "projected_away_points", "projected_home_points", "projected_total",
        "structural_total_sigma", "reliability", "analysis_line",
        "over_probability", "under_probability", "feature_coverage",
    ):
        assert out[key] == base[key]
    assert out["upgrade_step11_applied"] is False
    assert out["form_strength_reason"] == "sample low"
