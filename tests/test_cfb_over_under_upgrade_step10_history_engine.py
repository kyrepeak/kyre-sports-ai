"""Regression checks for CFB O/U Upgrade Step 10 historical context engine."""
from __future__ import annotations

from datetime import datetime, timezone

import cfb_over_under_history_engine_v1 as hist


def _event(event_id, date, team_id="50", opp_id="2390", pf=9, pa=56, completed=True):
    return {
        "id": str(event_id),
        "date": date,
        "status": {"type": {"completed": completed, "name": "STATUS_FINAL" if completed else "STATUS_SCHEDULED"}},
        "competitions": [{
            "id": str(event_id),
            "competitors": [
                {"homeAway": "away", "team": {"id": str(team_id), "displayName": "Florida A&M Rattlers"}, "score": {"value": pf}},
                {"homeAway": "home", "team": {"id": str(opp_id), "displayName": "Miami Hurricanes"}, "score": {"value": pa}},
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


def test_event_row_requires_completed_exact_team_identity():
    row = hist._event_row(_event("401635536", "2024-09-08T01:00:00Z"), "50")
    assert row["opponent_id"] == "2390"
    assert row["points_for"] == 9.0
    assert row["points_against"] == 56.0
    assert row["combined_total"] == 65.0
    assert hist._event_row(_event("x", "2026-09-11T00:00:00Z", completed=False), "50") is None
    assert hist._event_row(_event("x", "2024-09-08T01:00:00Z"), "999") is None


def test_load_history_excludes_future_and_target_event(monkeypatch):
    payload = {"events": [
        _event("old", "2024-09-08T01:00:00Z"),
        _event("target", "2026-09-11T00:00:00Z"),
        _event("future", "2026-09-20T00:00:00Z"),
    ]}
    monkeypatch.setattr(hist, "_fetch_team_schedule", lambda team_id, season: (payload, []))
    rows, _ = hist._load_history(
        "50", [2026], datetime(2026, 9, 11, 0, 0, tzinfo=timezone.utc), excluded_event_id="target"
    )
    assert [row["event_id"] for row in rows] == ["old"]


def test_recent_summary_and_h2h_are_descriptive():
    rows = []
    for idx, total in enumerate((40, 45, 50, 55, 60, 65, 70, 75), start=1):
        rows.append({
            "event_id": str(idx), "opponent_id": "x", "points_for": total - 20,
            "points_against": 20.0, "combined_total": float(total), "won": total - 20 > 20,
        })
    summary = hist._summary(rows)
    assert summary["ready"] is True
    assert summary["games"] == 8
    assert summary["avg_combined_total"] == 57.5
    h2h = hist._h2h_summary([rows[0] | {"opponent_id": "2390"}], "2390")
    assert h2h["ready"] is True
    assert h2h["meetings"] == 1


def test_build_history_engine_uses_exact_step9_ids_and_h2h(monkeypatch):
    away_events = []
    home_events = []
    for idx in range(8):
        away_events.append(_event(f"a{idx}", f"2025-{12-idx:02d}-01T20:00:00Z", pf=20+idx, pa=17+idx, opp_id=f"9{idx}"))
        home_events.append(_event(f"h{idx}", f"2025-{12-idx:02d}-02T20:00:00Z", team_id="2390", opp_id=f"8{idx}", pf=30+idx, pa=14+idx))
    away_events.append(_event("401635536", "2024-09-08T01:00:00Z", pf=9, pa=56, opp_id="2390"))

    def fetch(team_id, season):
        if str(team_id) == "50":
            return {"events": away_events if season in (2024, 2025, 2026) else []}, []
        return {"events": home_events if season in (2024, 2025, 2026) else []}, []

    monkeypatch.setattr(hist, "_fetch_team_schedule", fetch)
    env = {"event_id": "401858213", "away_espn_team_id": "50", "home_espn_team_id": "2390"}
    out = hist.build_history_engine(_game(), {"team": "Florida A&M"}, {"team": "Miami (FL)"}, step9_environment=env)
    assert out["model_ready"] is True
    assert out["away_recent"]["games"] == 8
    assert out["home_recent"]["games"] == 8
    assert out["head_to_head"]["meetings"] >= 1
    assert out["head_to_head"]["latest"]["event_id"] == "401635536"
    assert out["future_event_leakage_allowed"] is False
    assert out["projected_total_history_weight"] == 0.0
    assert out["selection_history_weight"] == 0.0


def test_build_history_engine_fails_closed_without_step9_team_ids():
    out = hist.build_history_engine(_game(), {}, {}, step9_environment={"event_id": "x"})
    assert out["model_ready"] is False
    assert out["coverage"] == 0.0
    assert "team IDs" in out["reason"]


def test_apply_to_raw_preserves_all_step9_math():
    base = {
        "version": "STEP9", "ready": True,
        "projected_away_points": 20.0, "projected_home_points": 27.0,
        "projected_total": 47.0, "structural_total_sigma": 14.2,
        "over_probability": 0.41, "under_probability": 0.59, "push_probability": 0.0,
        "reliability": 0.73, "analysis_line": 50.5,
        "feature_coverage": {"score": 0.81}, "components": {"step9_environment_sigma_adjustment": 0.2},
    }
    engine = {
        "model_ready": True, "coverage": 1.0,
        "away_recent": {"games": 8}, "home_recent": {"games": 8},
        "head_to_head": {"meetings": 1},
    }
    out = hist.apply_to_raw(base, engine)
    for key in (
        "projected_away_points", "projected_home_points", "projected_total",
        "structural_total_sigma", "over_probability", "under_probability",
        "push_probability", "reliability", "analysis_line",
    ):
        assert out[key] == base[key]
    assert out["feature_coverage"] == base["feature_coverage"]
    assert out["components"]["step9_environment_sigma_adjustment"] == 0.2
    assert out["components"]["step10_projected_total_adjustment"] == 0.0
    assert out["components"]["step10_structural_sigma_adjustment"] == 0.0
    assert out["projected_total_history_weight"] == 0.0
    assert out["analysis_line_history_weight"] == 0.0
    assert out["selection_history_weight"] == 0.0


def test_history_cache_clear_is_safe(monkeypatch):
    seen = []
    monkeypatch.setattr(hist._fetch_team_schedule, "clear", lambda: seen.append(True), raising=False)
    hist.clear_history_engine_cache()
    assert seen == [True]
