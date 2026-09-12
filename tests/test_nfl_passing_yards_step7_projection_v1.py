from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_projection_v1 as projection


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _fixture_inputs():
    qb_ctx = {"qb1": {"athlete_id": "999", "name": "Verified QB"}}
    qb_profile = {
        "ready": True,
        "athlete_id": "999",
        "qb_name": "Verified QB",
        "season": {"attempts_per_game": 35.0, "yards_per_attempt": 8.0},
        "recent3_attempts": 40.0,
        "recent3_yards": 300.0,
    }
    defense_profile = {
        "ready": True,
        "team_id": "34",
        "team_name": "Opponent",
        "season": {"passing_attempts_allowed_per_game": 38.0, "yards_per_attempt_allowed": 7.0},
        "recent3_ypa_allowed": 6.8,
    }
    pressure_ctx = {"pressure_label": "MODERATE"}
    personnel_ctx = {"personnel_label": "NEUTRAL"}
    environment_ctx = {
        "away_pace": {"pass_attempts_per_game": 37.0},
        "environment_label": "NEUTRAL",
        "weather_label": "NORMAL",
    }
    return qb_ctx, qb_profile, defense_profile, pressure_ctx, personnel_ctx, environment_ctx


def test_step7_weighted_blend_renormalizes_only_available_inputs() -> None:
    values = {"a": 10.0, "b": float("nan"), "c": 30.0}
    weights = {"a": 0.5, "b": 0.3, "c": 0.2}
    out = projection.weighted_blend(values, weights)
    assert round(out["coverage"], 6) == 0.7
    assert round(out["value"], 6) == round((10.0 * 0.5 + 30.0 * 0.2) / 0.7, 6)
    assert out["used_count"] == 2
    assert round(sum(row["normalized_weight"] for row in out["used"]), 8) == 1.0


def test_step7_full_verified_projection_is_volume_times_efficiency() -> None:
    args = _fixture_inputs()
    out = projection.build_baseline_projection(*args, side="away", preseason=False)
    assert out["ready"] is True
    assert out["coverage_grade"] == "GREEN"
    assert round(out["expected_attempts"], 2) == 36.90
    assert round(out["expected_ypa"], 2) == 7.53
    assert round(out["projection_yards"], 2) == 277.86
    assert out["attempt_coverage"] == 1.0
    assert out["ypa_coverage"] == 1.0
    assert out["sportsbook_influence"] == 0.0
    assert out["context_adjustment_yards"] == 0.0
    assert out["monte_carlo_enabled"] is False


def test_step7_pressure_personnel_weather_labels_do_not_change_baseline() -> None:
    args = list(_fixture_inputs())
    baseline = projection.build_baseline_projection(*args, side="away", preseason=False)
    args[3] = {"pressure_label": "HIGH PRESSURE"}
    args[4] = {"personnel_label": "HURT"}
    args[5] = dict(args[5], environment_label="WATCH", weather_label="WATCH")
    changed_labels = projection.build_baseline_projection(*args, side="away", preseason=False)
    assert baseline["projection_yards"] == changed_labels["projection_yards"]
    assert changed_labels["pressure_context"] == "HIGH PRESSURE"
    assert changed_labels["personnel_context"] == "HURT"
    assert changed_labels["weather_context"] == "WATCH"
    assert changed_labels["context_adjustment_yards"] == 0.0


def test_step7_preseason_projection_fails_closed() -> None:
    args = _fixture_inputs()
    out = projection.build_baseline_projection(*args, side="away", preseason=True)
    assert out["ready"] is False
    assert "preseason workload" in out["reason"]
    assert out["sportsbook_influence"] == 0.0


def test_step7_requires_verified_qb_and_opponent_identity() -> None:
    args = list(_fixture_inputs())
    args[0] = {"qb1": {"athlete_id": "fake", "name": "Fake QB"}}
    out = projection.build_baseline_projection(*args, side="away", preseason=False)
    assert out["ready"] is False
    assert "verified ESPN quarterback athlete ID" in out["reason"]

    args = list(_fixture_inputs())
    args[2] = dict(args[2], team_id="synthetic")
    out = projection.build_baseline_projection(*args, side="away", preseason=False)
    assert out["ready"] is False
    assert "verified ESPN opponent team ID" in out["reason"]


def test_step7_low_source_coverage_withholds_projection() -> None:
    args = list(_fixture_inputs())
    profile = dict(args[1])
    profile["recent3_attempts"] = float("nan")
    profile["recent3_yards"] = float("nan")
    profile["season"] = {"attempts_per_game": 35.0, "yards_per_attempt": 8.0}
    args[1] = profile
    defense_profile = dict(args[2])
    defense_profile["season"] = {"passing_attempts_allowed_per_game": float("nan"), "yards_per_attempt_allowed": float("nan")}
    defense_profile["recent3_ypa_allowed"] = float("nan")
    args[2] = defense_profile
    args[5] = dict(args[5], away_pace={"pass_attempts_per_game": float("nan")})
    out = projection.build_baseline_projection(*args, side="away", preseason=False)
    assert out["ready"] is False
    assert out["coverage_grade"] == "CHECK"
    assert out["attempt_coverage"] == 0.45
    assert out["ypa_coverage"] == 0.45


def test_router_v87_advances_only_passing_yards_step7() -> None:
    hub = _read("nfl_hub_v26.py")
    router = _read("streamlit_memory_lazy_router_v87.py")
    app = _read("app.py")
    page = _read("nfl_passing_yards_hub_v8.py")
    engine = _read("nfl_passing_yards_projection_v1.py")

    assert "import nfl_hub_v25 as base" in hub
    assert "nfl_passing_yards_hub_v8" in hub
    assert "import streamlit_memory_lazy_router_v86 as prior" in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v26"' in router
    assert "streamlit_memory_lazy_router_v87" in app
    assert "STREAMLIT_MAIN_V86_NFL_PASSING_YARDS_STEP6_ENVIRONMENT_2026-09-11" in app
    assert "STREAMLIT_MAIN_V87_NFL_PASSING_YARDS_STEP7_BASELINE_PROJECTION_2026-09-11" in app
    assert "STEP 7 BASELINE PROJECTION GREEN" in page
    assert "sportsbook influence 0.0%" in page
    assert "pressure/personnel/weather label adjustment 0.0" in page
    assert "Monte Carlo/probability/fair-line/EV/ranking/recommendation OFF" in page
    assert "Sportsbook" in engine or "sportsbook" in engine
    assert '"sportsbook_influence": 0.0' in engine
    assert '"context_adjustment_yards": 0.0' in engine
    assert "Preseason remains fail-closed" in engine
