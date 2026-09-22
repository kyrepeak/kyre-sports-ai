"""Regression checks for College Football Step 8 Over/Under Hub V2."""
from __future__ import annotations

import inspect

import cfb_over_under_hub_v2 as hub


def _game():
    return {
        "away_team": "Oklahoma",
        "home_team": "Michigan",
    }


def _profile(team):
    return {"team": team}


def _output():
    return {
        "ready": True,
        "projected_total": 52.4,
        "projected_away_points": 25.1,
        "projected_home_points": 27.3,
        "analysis_line": 50.5,
        "over_probability": 0.56,
        "under_probability": 0.44,
        "push_probability": 0.0,
        "model_lean": "OVER",
        "confidence": "MEDIUM",
        "reliability": 0.82,
        "sample_factor": 0.80,
        "feature_coverage": {"score": 0.80},
        "structural_total_sigma": 14.2,
        "total_uncertainty_90": {"low": 29.0, "high": 75.8},
        "components": {
            "away_base_points": 24.0,
            "home_base_points": 26.0,
            "away_recent_adjustment": 0.5,
            "home_recent_adjustment": 0.8,
            "away_efficiency_adjustment": 0.7,
            "home_efficiency_adjustment": 0.6,
        },
    }


def test_model_card_shows_projection_probability_and_zero_line_weight():
    html = hub._model_card(
        _game(),
        _profile("Oklahoma"),
        _profile("Michigan"),
        _output(),
    )

    assert "RAW OVER/UNDER MODEL V1" in html
    assert "Projected game total" in html
    assert "52.4" in html
    assert "P(Over)" in html
    assert "56.0%" in html
    assert "P(Under)" in html
    assert "44.0%" in html
    assert "0%" in html
    assert "Analysis-line projection weight" in html
    assert "NOT FINAL PICK" in html


def test_gated_model_card_does_not_invent_projection():
    html = hub._model_card(
        _game(),
        _profile("Oklahoma"),
        _profile("Michigan"),
        {"ready": False, "reasons": ["game is not verified pregame"]},
    )
    assert "TOTAL MODEL GATED" in html
    assert "game is not verified pregame" in html
    assert "No projected total" in html


def test_component_panel_exposes_audit_inputs():
    html = hub._components_panel(_output())
    assert "MODEL COMPONENT AUDIT" in html
    assert "Away base points" in html
    assert "Home base points" in html
    assert "Away recent adj" in html
    assert "Home efficiency adj" in html
    assert "Structural total sigma" in html


def test_hub_uses_manual_threshold_and_no_slate_ranking():
    source = inspect.getsource(hub)

    assert hub.FROZEN_OVER_UNDER_HUB == "cfb_over_under_hub_v1"
    assert hub.MARKET == "Over/Under"

    required = (
        "st.number_input",
        "model.project_matchup",
        "analysis total line",
        "0% projection weight",
        "Step 9",
    )
    lower = source.lower()
    for token in required:
        assert token.lower() in lower

    forbidden = (
        "scan_slate",
        "rank_slate",
        "top-5 scanner",
        "sportsbook_price",
        "expected_value",
        "np.random",
        "import numpy",
    )
    for token in forbidden:
        assert token.lower() not in lower
