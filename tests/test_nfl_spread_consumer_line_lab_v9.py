from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _analytics():
    return {
        "ready": True,
        "projected_away_margin": 3.2,
        "margin_distribution": {"-1": 0.10, "0": 0.15, "1": 0.25, "2": 0.25, "3": 0.25},
        "simulations": 5_000_000,
        "certified_run": True,
        "sportsbook_projection_influence": 0.0,
    }


def test_line_lab_regrades_half_point_without_mutating_model():
    from nfl_spread_line_lab_v1 import settle_line
    analytics = _analytics()
    before = dict(analytics)
    out = settle_line(analytics, -1.5, price=-110)
    assert out["away_cover_probability"] == pytest.approx(0.50)
    assert out["push_probability"] == pytest.approx(0.0)
    assert out["home_cover_probability"] == pytest.approx(0.50)
    assert out["selected_away_spread"] == -1.5
    assert out["projected_away_margin"] == 3.2
    assert analytics == before


def test_line_lab_handles_whole_number_push_and_non_push_cover():
    from nfl_spread_line_lab_v1 import settle_line
    out = settle_line(_analytics(), -1.0, price=-110)
    assert out["away_cover_probability"] == pytest.approx(0.50)
    assert out["push_probability"] == pytest.approx(0.25)
    assert out["home_cover_probability"] == pytest.approx(0.25)
    assert out["away_cover_probability_non_push"] == pytest.approx(2 / 3)
    assert 0.52 < out["break_even_probability"] < 0.53
    assert out["probability_edge"] > 0


def test_line_lab_fails_closed_without_distribution():
    from nfl_spread_line_lab_v1 import settle_line
    out = settle_line({"ready": True, "projected_away_margin": 1.0}, -3.5)
    assert out["ready"] is False
    assert "distribution" in out["error"].lower()


def test_v9_contract_and_runtime_route_are_consumer_first():
    page = (ROOT / "nfl_spread_hub_v9.py").read_text(encoding="utf-8")
    loader = (ROOT / "universal_runtime_v5_loader_v21.py").read_text(encoding="utf-8")
    assert 'route.sport_id == "nfl" and route.market_id == "spread"' in loader
    assert '"nfl_spread_hub_v9"' in loader
    assert "st.slider(" in page
    assert "min_value=-30.5" in page
    assert "max_value=30.5" in page
    assert "step=0.5" in page
    assert "Advanced Diagnostics" in page
    assert "st.date_input(" not in page
    forbidden = (
        "STEP 1A PASSED",
        "Step 2 — QB Depth + Current Availability",
        "Step 3 — Preseason Game-Plan Intelligence",
        "Step 4 — Team-Strength Win Model",
    )
    assert not any(text in page for text in forbidden)
