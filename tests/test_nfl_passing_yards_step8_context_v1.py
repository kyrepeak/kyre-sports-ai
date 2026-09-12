from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_context_v1 as context


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _fixture():
    step7 = {
        "ready": True,
        "qb_name": "Verified QB",
        "projection_yards": 280.0,
        "expected_attempts": 35.0,
        "expected_ypa": 8.0,
        "coverage_grade": "GREEN",
        "attempt_components": [
            {"value": 35.0}, {"value": 40.0}, {"value": 38.0}, {"value": 37.0},
        ],
        "ypa_components": [
            {"value": 8.0}, {"value": 7.5}, {"value": 7.0}, {"value": 6.8},
        ],
    }
    qb_profile = {"recent_games": [
        {"passing_yards": 300.0},
        {"passing_yards": 280.0},
        {"passing_yards": 260.0},
        {"passing_yards": 310.0},
        {"passing_yards": 250.0},
    ]}
    pressure = {
        "ready": True,
        "offense": {"sack_rate_allowed": 6.0},
        "defense": {"sack_rate_generated": 10.0},
    }
    personnel = {"qb_status": "No listed injury", "personnel_label": "NEUTRAL"}
    environment = {
        "weather_label": "CONTROLLED",
        "away_rest": {"turnaround_days": 7, "rest_label": "STANDARD"},
    }
    return step7, qb_profile, pressure, personnel, environment


def test_step8_pressure_adjustment_is_mechanical_and_bounded() -> None:
    step7, _, pressure, _, _ = _fixture()
    out = context.pressure_opportunity_adjustment(step7, pressure)
    assert out["ready"] is True
    assert out["matchup_sack_rate_pct"] == 8.0
    assert out["raw_delta_pct_points"] == 2.0
    assert out["bounded_delta_pct_points"] == 2.0
    assert out["attempt_adjustment"] == -0.7
    assert out["yard_adjustment"] == -5.6
    assert out["cap_hit"] is False


def test_step8_pressure_delta_hard_cap_prevents_runaway_adjustment() -> None:
    step7, _, pressure, _, _ = _fixture()
    pressure["offense"]["sack_rate_allowed"] = 2.0
    pressure["defense"]["sack_rate_generated"] = 20.0
    out = context.pressure_opportunity_adjustment(step7, pressure)
    assert out["raw_delta_pct_points"] == 9.0
    assert out["bounded_delta_pct_points"] == context.MAX_SACK_RATE_DELTA_PCT
    assert out["cap_hit"] is True
    assert out["attempt_adjustment"] == -1.75
    assert out["yard_adjustment"] == -14.0


def test_step8_recent_variability_is_descriptive_not_probability() -> None:
    profile = {"recent_games": [
        {"passing_yards": 100.0},
        {"passing_yards": 200.0},
        {"passing_yards": 300.0},
    ]}
    out = context.recent_variability_band(profile, 200.0)
    assert out["ready"] is True
    assert out["sample_std_yards"] == 100.0
    assert out["lower"] == 100.0
    assert out["upper"] == 300.0
    assert "descriptive only" in out["basis"]


def test_step8_source_disagreement_uses_verified_step7_component_extremes() -> None:
    step7, _, _, _, _ = _fixture()
    out = context.source_disagreement_band(step7, 280.0)
    assert out["ready"] is True
    assert out["lower"] == 35.0 * 6.8
    assert out["upper"] == 40.0 * 8.0
    assert "descriptive only" in out["basis"]


def test_step8_context_projection_moves_only_pressure_opportunity() -> None:
    args = _fixture()
    out = context.build_context_projection(*args, side="away", preseason=False)
    assert out["ready"] is True
    assert out["context_attempts"] == 34.3
    assert out["pressure_adjustment_yards"] == -5.6
    assert out["context_projection_yards"] == 274.4
    assert out["personnel_adjustment_yards"] == 0.0
    assert out["weather_adjustment_yards"] == 0.0
    assert out["rest_adjustment_yards"] == 0.0
    assert out["sportsbook_influence"] == 0.0
    assert out["monte_carlo_enabled"] is False
    assert out["probability_enabled"] is False
    assert out["uncertainty"]["ready"] is True
    assert "NOT A PROBABILITY INTERVAL" in out["uncertainty"]["band_type"]


def test_step8_personnel_weather_rest_labels_do_not_change_central_number() -> None:
    args = list(_fixture())
    baseline = context.build_context_projection(*args, side="away", preseason=False)
    args[3] = {"qb_status": "No listed injury", "personnel_label": "HURT"}
    args[4] = {"weather_label": "WATCH", "away_rest": {"turnaround_days": 4, "rest_label": "SHORT"}}
    changed = context.build_context_projection(*args, side="away", preseason=False)
    assert changed["context_projection_yards"] == baseline["context_projection_yards"]
    assert changed["personnel_adjustment_yards"] == 0.0
    assert changed["weather_adjustment_yards"] == 0.0
    assert changed["rest_adjustment_yards"] == 0.0
    assert changed["confidence"] == "LOW"


def test_step8_verified_hard_qb_status_blocks_full_game_projection() -> None:
    args = list(_fixture())
    args[3] = {"qb_status": "Out", "personnel_label": "HURT"}
    out = context.build_context_projection(*args, side="away", preseason=False)
    assert out["ready"] is False
    assert "blocks a full-game contextual projection" in out["reason"]
    assert out["sportsbook_influence"] == 0.0


def test_step8_preseason_remains_fail_closed() -> None:
    out = context.build_context_projection(*_fixture(), side="away", preseason=True)
    assert out["ready"] is False
    assert "preseason workload remains uncertified" in out["reason"]


def test_step8_route_preserves_step7_and_other_markets() -> None:
    hub = _read("nfl_hub_v27.py")
    router = _read("streamlit_memory_lazy_router_v88.py")
    app = _read("app.py")
    page = _read("nfl_passing_yards_hub_v9.py")
    engine = _read("nfl_passing_yards_context_v1.py")

    assert "import nfl_hub_v26 as base" in hub
    assert "nfl_passing_yards_hub_v9" in hub
    assert "import streamlit_memory_lazy_router_v87 as prior" in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v27"' in router
    assert "streamlit_memory_lazy_router_v88" in app
    assert "STREAMLIT_MAIN_V87_NFL_PASSING_YARDS_STEP7_BASELINE_PROJECTION_2026-09-11" in app
    assert "STREAMLIT_MAIN_V88_NFL_PASSING_YARDS_STEP8_CONTEXT_UNCERTAINTY_2026-09-11" in app
    assert "STEP 8 CONTEXT + UNCERTAINTY GREEN" in page
    assert "Certified V8 / Steps 1–7 are rendered unchanged" in page
    assert "prior.render_nfl_passing_yards_hub()" in page
    assert "finally:" in page and "prior.projection.build_baseline_projection = original" in page
    assert "sportsbook influence = 0.0%" in page
    assert "personnel/weather/rest numerical adjustment = 0.0" in page
    assert '"sportsbook_influence": 0.0' in engine
    assert '"personnel_adjustment_yards": 0.0' in engine
    assert "NOT A PROBABILITY INTERVAL" in engine
    assert "MAX_SACK_RATE_DELTA_PCT = 5.0" in engine
