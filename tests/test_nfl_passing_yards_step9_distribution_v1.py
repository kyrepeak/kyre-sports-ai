from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_distribution_v1 as distribution


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _step8_fixture(confidence: str = "HIGH", games: int = 5, sigma: float = 55.0) -> dict:
    return {
        "ready": True,
        "qb_name": "Verified QB",
        "context_projection_yards": 275.0,
        "confidence": confidence,
        "uncertainty": {
            "recent": {
                "ready": True,
                "games": games,
                "sample_std_yards": sigma,
            },
            "source": {
                "ready": True,
                "lower": 220.0,
                "upper": 340.0,
            },
        },
        "sportsbook_influence": 0.0,
    }


def test_step9_zero_truncated_normal_never_assigns_cdf_below_zero() -> None:
    assert distribution.truncated_normal_cdf(-1.0, 50.0, 100.0) == 0.0
    assert distribution.truncated_normal_cdf(0.0, 50.0, 100.0) == 0.0
    q10 = distribution.truncated_normal_quantile(0.10, 20.0, 100.0)
    assert q10 >= 0.0


def test_step9_quantiles_are_monotonic_and_median_tracks_location_when_truncation_is_tiny() -> None:
    qs = [distribution.truncated_normal_quantile(p, 275.0, 55.0) for p in (0.10, 0.25, 0.50, 0.75, 0.90)]
    assert qs == sorted(qs)
    assert abs(qs[2] - 275.0) < 0.01


def test_step9_threshold_probabilities_are_complementary_and_monotonic() -> None:
    low = distribution.threshold_probability(200.0, 275.0, 55.0)
    high = distribution.threshold_probability(300.0, 275.0, 55.0)
    assert low["ready"] is True
    assert high["ready"] is True
    assert abs(low["over_probability"] + low["under_probability"] - 1.0) < 1e-12
    assert low["over_probability"] > high["over_probability"]


def test_step9_builds_analytic_probability_distribution_from_recent_observed_sd_only() -> None:
    out = distribution.build_distribution(_step8_fixture())
    assert out["ready"] is True
    assert out["distribution"] == "ZERO-TRUNCATED NORMAL"
    assert out["location_yards"] == 275.0
    assert out["sigma_yards"] == 55.0
    assert out["recent_games"] == 5
    assert out["confidence"] == "HIGH"
    assert out["probability_enabled"] is True
    assert out["monte_carlo_enabled"] is False
    assert out["simulation_count"] == 0
    assert out["sampling_error"] == 0.0
    assert out["sportsbook_influence"] == 0.0
    assert out["fair_odds_enabled"] is False
    assert out["ev_enabled"] is False
    assert out["ranking_enabled"] is False
    assert out["recommendation_enabled"] is False
    assert len(out["thresholds"]) == len(distribution.DEFAULT_THRESHOLDS)
    assert set(out["quantiles"]) == {"p10", "p25", "p50", "p75", "p90"}


def test_step9_does_not_convert_source_disagreement_into_probability_when_recent_variance_missing() -> None:
    step8 = _step8_fixture(games=2, sigma=55.0)
    out = distribution.build_distribution(step8)
    assert out["ready"] is False
    assert "at least 3 verified recent games" in out["reason"]
    assert out["probability_enabled"] is False

    step8 = _step8_fixture(games=5, sigma=0.0)
    out = distribution.build_distribution(step8)
    assert out["ready"] is False
    assert "non-zero observed variance" in out["reason"]


def test_step9_withholds_probability_when_step8_is_withheld() -> None:
    step8 = _step8_fixture()
    step8["ready"] = False
    out = distribution.build_distribution(step8)
    assert out["ready"] is False
    assert out["reason"] == "Step 8 contextual projection is required"
    assert out["probability_enabled"] is False


def test_step9_probability_confidence_is_evidence_quality_not_probability_accuracy() -> None:
    assert distribution.probability_confidence(_step8_fixture(confidence="HIGH", games=5), 5)[0] == "HIGH"
    assert distribution.probability_confidence(_step8_fixture(confidence="MEDIUM", games=4), 4)[0] == "MEDIUM"
    assert distribution.probability_confidence(_step8_fixture(confidence="LOW", games=3), 3)[0] == "LOW"
    assert distribution.probability_confidence(_step8_fixture(confidence="CHECK", games=5), 5)[0] == "CHECK"


def test_router_v89_advances_only_passing_yards_step9() -> None:
    hub = _read("nfl_hub_v28.py")
    router = _read("streamlit_memory_lazy_router_v89.py")
    app = _read("app.py")
    page = _read("nfl_passing_yards_hub_v10.py")
    engine = _read("nfl_passing_yards_distribution_v1.py")

    assert "import nfl_hub_v27 as base" in hub
    assert "nfl_passing_yards_hub_v10" in hub
    assert "import streamlit_memory_lazy_router_v88 as prior" in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v28"' in router
    assert "streamlit_memory_lazy_router_v89" in app
    assert "STREAMLIT_MAIN_V88_NFL_PASSING_YARDS_STEP8_CONTEXT_UNCERTAINTY_2026-09-11" in app
    assert "STREAMLIT_MAIN_V89_NFL_PASSING_YARDS_STEP9_DISTRIBUTION_PROBABILITY_2026-09-11" in app
    assert "STEP 9 DISTRIBUTION + PROBABILITY GREEN" in page
    assert "sportsbook influence 0.0%" in page
    assert "Monte Carlo = OFF by design" in page
    assert "fair odds/EV/ranking/recommendation OFF" in page
    assert '"sportsbook_influence": 0.0' in engine
    assert '"monte_carlo_enabled": False' in engine
    assert '"fair_odds_enabled": False' in engine
    assert "does not reinterpret" in engine
